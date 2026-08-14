"""User management endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    Action,
    AuthContext,
    CurrentUserDep,
    Resource,
    require_permission,
)
from src.db import get_db_unscoped
from src.schemas.common import (
    ApiResponse,
    PaginationParams,
    build_pagination_meta,
)
from src.schemas.users import (
    PasswordChange,
    ServiceAccountCreate,
    ServiceAccountCreated,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from src.services import users as user_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/users", tags=["users"])


def _assert_same_tenant_or_platform(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot operate on another tenant's users",
        )


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.READ))
    ],
    include_service_accounts: bool = Query(default=True),
) -> ApiResponse[list[UserResponse]]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    rows, total = await user_service.list_users(
        db,
        tenant_id,
        limit=pagination.page_size,
        offset=pagination.offset,
        include_service_accounts=include_service_accounts,
    )
    return ApiResponse(
        data=[UserResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(
            total_count=total, page=pagination.page, page_size=pagination.page_size
        ),
    )


@router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    tenant_id: UUID,
    payload: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.CREATE))
    ],
) -> ApiResponse[UserResponse]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user = await user_service.create_user(db, tenant_id, payload)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    tenant_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.READ))
    ],
) -> ApiResponse[UserResponse]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user = await user_service.get_user(db, user_id)
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found in this tenant",
        )
    return ApiResponse(data=UserResponse.model_validate(user))


@router.patch("/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(
    tenant_id: UUID,
    user_id: UUID,
    payload: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.UPDATE))
    ],
) -> ApiResponse[UserResponse]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user = await user_service.get_user(db, user_id)
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found in this tenant",
        )
    user = await user_service.update_user(db, user_id, payload)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    tenant_id: UUID,
    user_id: UUID,
    payload: PasswordChange,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: CurrentUserDep,
) -> None:
    # Users may only change their own password; a tenant admin can reset any
    # user in their tenant.
    _assert_same_tenant_or_platform(auth, tenant_id)
    if auth.user_id != user_id and not auth.is_platform_admin:
        # Tenant admin reset flow: allowed for tenant admins only
        # (RBAC dependency would deny otherwise)
        from src.auth.rbac import Action, Resource, has_permission

        if not has_permission(auth, Resource.USER, Action.UPDATE):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change another user's password",
            )
    await user_service.change_password(db, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    tenant_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.DELETE))
    ],
) -> None:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user = await user_service.get_user(db, user_id)
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found in this tenant",
        )
    await user_service.deactivate_user(db, user_id)


@router.post(
    "/service-accounts",
    response_model=ApiResponse[ServiceAccountCreated],
    status_code=status.HTTP_201_CREATED,
)
async def create_service_account(
    tenant_id: UUID,
    payload: ServiceAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.CREATE))
    ],
) -> ApiResponse[ServiceAccountCreated]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user, api_key = await user_service.create_service_account(db, tenant_id, payload)
    return ApiResponse(
        data=ServiceAccountCreated(
            user=UserResponse.model_validate(user),
            api_key=api_key,
        )
    )


@router.post(
    "/service-accounts/{user_id}/rotate-key",
    response_model=ApiResponse[dict[str, str]],
)
async def rotate_api_key(
    tenant_id: UUID,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.USER, Action.UPDATE))
    ],
) -> ApiResponse[dict[str, str]]:
    _assert_same_tenant_or_platform(auth, tenant_id)
    user = await user_service.get_user(db, user_id)
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service account {user_id} not found in this tenant",
        )
    new_key = await user_service.rotate_api_key(db, user_id)
    return ApiResponse(data={"api_key": new_key})


__all__ = ["router"]

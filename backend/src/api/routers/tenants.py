"""Tenant management endpoints (platform admin only for create/delete)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from src.schemas.tenants import TenantCreate, TenantResponse, TenantUpdate
from src.services import tenants as tenant_service

router = APIRouter(prefix="/api/v1/admin/tenants", tags=["tenants"])


def _require_platform_admin() -> AuthContext:
    """Dependency factory that returns 403 unless the caller is platform admin."""

    async def _dep(auth: CurrentUserDep) -> AuthContext:
        if not auth.is_platform_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform administrator role required",
            )
        return auth

    return _dep  # type: ignore[return-value]


@router.get("", response_model=ApiResponse[list[TenantResponse]])
async def list_tenants(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin())],
) -> ApiResponse[list[TenantResponse]]:
    rows, total = await tenant_service.list_tenants(
        db, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[TenantResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(
            total_count=total, page=pagination.page, page_size=pagination.page_size
        ),
    )


@router.post(
    "",
    response_model=ApiResponse[TenantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    payload: TenantCreate,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin())],
) -> ApiResponse[TenantResponse]:
    tenant = await tenant_service.create_tenant(db, payload)
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.get("/{tenant_id}", response_model=ApiResponse[TenantResponse])
async def get_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TENANT, Action.READ))
    ],
) -> ApiResponse[TenantResponse]:
    # Platform admin can read any tenant; tenant admin can only read their own
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot read another tenant",
        )
    tenant = await tenant_service.get_tenant(db, tenant_id)
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.patch("/{tenant_id}", response_model=ApiResponse[TenantResponse])
async def update_tenant(
    tenant_id: UUID,
    payload: TenantUpdate,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TENANT, Action.UPDATE))
    ],
) -> ApiResponse[TenantResponse]:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify another tenant",
        )
    tenant = await tenant_service.update_tenant(db, tenant_id, payload)
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin())],
) -> None:
    await tenant_service.delete_tenant(db, tenant_id)


__all__ = ["router"]

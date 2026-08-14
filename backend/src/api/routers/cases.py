"""Case management endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    Action,
    AuthContext,
    Resource,
    require_permission,
)
from src.db import get_db
from src.schemas.cases import (
    CaseClose,
    CaseCreate,
    CaseListFilters,
    CaseMerge,
    CaseResponse,
    CaseSeverity,
    CaseStatus,
    CaseUpdate,
)
from src.schemas.common import (
    ApiResponse,
    PaginationParams,
    build_pagination_meta,
)
from src.services import cases as case_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/cases", tags=["cases"])


def _assert_tenant_matches(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another tenant's cases",
        )


@router.get("", response_model=ApiResponse[list[CaseResponse]])
async def list_cases(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.READ))],
    status_filter: Annotated[CaseStatus | None, Query(alias="status")] = None,
    severity: CaseSeverity | None = None,
    assignee_id: UUID | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> ApiResponse[list[CaseResponse]]:
    _assert_tenant_matches(auth, tenant_id)
    filters = CaseListFilters(
        status=status_filter,
        severity=severity,
        assignee_id=assignee_id,
        tag=tag,
        search=search,
    )
    rows, total = await case_service.list_cases(
        db, tenant_id, filters, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[CaseResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(
            total_count=total, page=pagination.page, page_size=pagination.page_size
        ),
    )


@router.post("", response_model=ApiResponse[CaseResponse], status_code=status.HTTP_201_CREATED)
async def create_case(
    tenant_id: UUID,
    payload: CaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.CREATE))],
) -> ApiResponse[CaseResponse]:
    _assert_tenant_matches(auth, tenant_id)
    case = await case_service.create_case(
        db, tenant_id=tenant_id, created_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.get("/{case_id}", response_model=ApiResponse[CaseResponse])
async def get_case(
    tenant_id: UUID,
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.READ))],
) -> ApiResponse[CaseResponse]:
    _assert_tenant_matches(auth, tenant_id)
    case = await case_service.get_case(db, case_id)
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.patch("/{case_id}", response_model=ApiResponse[CaseResponse])
async def update_case(
    tenant_id: UUID,
    case_id: UUID,
    payload: CaseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.UPDATE))],
) -> ApiResponse[CaseResponse]:
    _assert_tenant_matches(auth, tenant_id)
    case = await case_service.update_case(db, case_id, payload, actor_id=auth.user_id)
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.post("/{case_id}/close", response_model=ApiResponse[CaseResponse])
async def close_case(
    tenant_id: UUID,
    case_id: UUID,
    payload: CaseClose,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.UPDATE))],
) -> ApiResponse[CaseResponse]:
    _assert_tenant_matches(auth, tenant_id)
    case = await case_service.close_case(db, case_id, payload, actor_id=auth.user_id)
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.post("/{case_id}/merge", response_model=ApiResponse[CaseResponse])
async def merge_cases(
    tenant_id: UUID,
    case_id: UUID,
    payload: CaseMerge,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.UPDATE))],
) -> ApiResponse[CaseResponse]:
    _assert_tenant_matches(auth, tenant_id)
    case = await case_service.merge_cases(db, case_id, payload, actor_id=auth.user_id)
    return ApiResponse(data=CaseResponse.model_validate(case))


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    tenant_id: UUID,
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE, Action.DELETE))],
) -> None:
    _assert_tenant_matches(auth, tenant_id)
    await case_service.delete_case(db, case_id)


__all__ = ["router"]

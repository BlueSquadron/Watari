"""Case template management endpoints.

Templates are tenant-scoped reusable case structures. Tenant admins
manage them; analysts can list and read them (to pick one at case
creation). Platform admins bypass tenant restrictions.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    Action,
    AuthContext,
    Resource,
    require_permission,
)
from src.db import get_db
from src.schemas.common import (
    ApiResponse,
    PaginationParams,
    build_pagination_meta,
)
from src.schemas.templates import (
    CaseTemplateCreate,
    CaseTemplateResponse,
    CaseTemplateUpdate,
)
from src.services import templates as template_service

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/case-templates",
    tags=["case-templates"],
)


def _assert_tenant_matches(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another tenant's case templates",
        )


@router.get("", response_model=ApiResponse[list[CaseTemplateResponse]])
async def list_case_templates(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE_TEMPLATE, Action.READ))],
) -> ApiResponse[list[CaseTemplateResponse]]:
    _assert_tenant_matches(auth, tenant_id)
    rows, total = await template_service.list_templates(
        db,
        tenant_id=tenant_id,
        limit=pagination.page_size,
        offset=pagination.offset,
    )
    return ApiResponse(
        data=[CaseTemplateResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(
            total_count=total,
            page=pagination.page,
            page_size=pagination.page_size,
        ),
    )


@router.post(
    "",
    response_model=ApiResponse[CaseTemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_case_template(
    tenant_id: UUID,
    payload: CaseTemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext,
        Depends(require_permission(Resource.CASE_TEMPLATE, Action.CREATE)),
    ],
) -> ApiResponse[CaseTemplateResponse]:
    _assert_tenant_matches(auth, tenant_id)
    template = await template_service.create_template(
        db,
        tenant_id=tenant_id,
        created_by=auth.user_id,
        payload=payload,
    )
    return ApiResponse(data=CaseTemplateResponse.model_validate(template))


@router.get(
    "/{template_id}",
    response_model=ApiResponse[CaseTemplateResponse],
)
async def get_case_template(
    tenant_id: UUID,
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.CASE_TEMPLATE, Action.READ))],
) -> ApiResponse[CaseTemplateResponse]:
    _assert_tenant_matches(auth, tenant_id)
    template = await template_service.get_template(db, tenant_id=tenant_id, template_id=template_id)
    return ApiResponse(data=CaseTemplateResponse.model_validate(template))


@router.patch(
    "/{template_id}",
    response_model=ApiResponse[CaseTemplateResponse],
)
async def update_case_template(
    tenant_id: UUID,
    template_id: UUID,
    payload: CaseTemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext,
        Depends(require_permission(Resource.CASE_TEMPLATE, Action.UPDATE)),
    ],
) -> ApiResponse[CaseTemplateResponse]:
    _assert_tenant_matches(auth, tenant_id)
    template = await template_service.update_template(
        db,
        tenant_id=tenant_id,
        template_id=template_id,
        payload=payload,
    )
    return ApiResponse(data=CaseTemplateResponse.model_validate(template))


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_case_template(
    tenant_id: UUID,
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext,
        Depends(require_permission(Resource.CASE_TEMPLATE, Action.DELETE)),
    ],
) -> None:
    _assert_tenant_matches(auth, tenant_id)
    await template_service.delete_template(db, tenant_id=tenant_id, template_id=template_id)


__all__ = ["router"]

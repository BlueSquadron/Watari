"""Report template and generation endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse
from src.schemas.reports import (
    ReportGenerateRequest,
    ReportResponse,
    ReportTemplateCreate,
    ReportTemplateResponse,
)
from src.services import reports as reports_service

templates_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/report-templates", tags=["reports"]
)
reports_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/reports", tags=["reports"]
)


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@templates_router.get("", response_model=ApiResponse[list[ReportTemplateResponse]])
async def list_templates(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.REPORT_TEMPLATE, Action.READ))
    ],
) -> ApiResponse[list[ReportTemplateResponse]]:
    _check(auth, tenant_id)
    rows = await reports_service.list_templates(db, tenant_id)
    return ApiResponse(data=[ReportTemplateResponse.model_validate(r) for r in rows])


@templates_router.post(
    "",
    response_model=ApiResponse[ReportTemplateResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_template(
    tenant_id: UUID,
    payload: ReportTemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.REPORT_TEMPLATE, Action.CREATE))
    ],
) -> ApiResponse[ReportTemplateResponse]:
    _check(auth, tenant_id)
    t = await reports_service.create_template(
        db,
        tenant_id=tenant_id,
        name=payload.name,
        type=payload.type.value,
        format=payload.format.value,
        template_content=payload.template_content,
        tag_schema=payload.tag_schema,
        created_by=auth.user_id,
    )
    return ApiResponse(data=ReportTemplateResponse.model_validate(t))


@reports_router.post(
    "",
    response_model=ApiResponse[ReportResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    tenant_id: UUID,
    case_id: UUID,
    payload: ReportGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.REPORT, Action.CREATE))],
) -> ApiResponse[ReportResponse]:
    _check(auth, tenant_id)
    report = await reports_service.generate_report(
        db,
        case_id=case_id,
        template_id=payload.template_id,
        format_override=payload.format.value if payload.format else None,
        generated_by=auth.user_id,
    )
    return ApiResponse(data=ReportResponse.model_validate(report))


@reports_router.get("/preview")
async def preview_report(
    tenant_id: UUID,
    case_id: UUID,
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.REPORT, Action.READ))],
) -> Response:
    _check(auth, tenant_id)
    rendered = await reports_service.preview_report(db, case_id=case_id, template_id=template_id)
    return Response(content=rendered, media_type="text/markdown")


__all__ = ["templates_router", "reports_router"]

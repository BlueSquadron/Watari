"""Audit log viewer endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.audit import AuditLogFilters, AuditLogResponse
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.services import audit as audit_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/audit-logs", tags=["audit"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[AuditLogResponse]])
async def list_logs(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.AUDIT_LOG, Action.READ))],
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> ApiResponse[list[AuditLogResponse]]:
    _check(auth, tenant_id)
    filters = AuditLogFilters(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        created_after=created_after,
        created_before=created_before,
    )
    rows, total = await audit_service.list_logs(
        db, tenant_id, filters, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[AuditLogResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


__all__ = ["router"]

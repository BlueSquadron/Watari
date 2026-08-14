"""Dashboard endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse
from src.schemas.dashboard import DashboardMetricsResponse
from src.services import dashboard as dashboard_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/dashboard", tags=["dashboard"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[DashboardMetricsResponse])
async def get_metrics(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.DASHBOARD, Action.READ))],
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> ApiResponse[DashboardMetricsResponse]:
    _check(auth, tenant_id)
    filters = dashboard_service.DashboardFilters(
        created_after=created_after, created_before=created_before
    )
    response = await dashboard_service.compute_metrics(db, tenant_id, filters)
    return ApiResponse(data=response)


__all__ = ["router"]

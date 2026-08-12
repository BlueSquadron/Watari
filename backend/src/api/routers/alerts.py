"""Alert endpoints.

The public contract is OCSF 1.8.0 Detection Finding. See
``src.schemas.alerts`` for the Pydantic shapes and
``docs/integration.md`` for worked examples.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.alerts import (
    AlertDismiss,
    AlertListFilters,
    AlertPromote,
    AlertResponse,
    AlertStatus,
    DetectionFindingIngest,
)
from src.schemas.cases import CaseResponse
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.services import alerts as alert_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/alerts", tags=["alerts"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[AlertResponse]])
async def list_alerts(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ALERT, Action.READ))
    ],
    workflow_status: Annotated[
        AlertStatus | None, Query(alias="status")
    ] = None,
    severity_id: Annotated[int | None, Query(ge=0, le=99)] = None,
    product_name: Annotated[str | None, Query(alias="product")] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> ApiResponse[list[AlertResponse]]:
    _check(auth, tenant_id)
    filters = AlertListFilters(
        workflow_status=workflow_status,
        severity_id=severity_id,
        product_name=product_name,
        created_after=created_after,
        created_before=created_before,
    )
    rows, total = await alert_service.list_alerts(
        db, tenant_id, filters, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[alert_service.alert_to_response(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post(
    "",
    response_model=ApiResponse[AlertResponse],
    status_code=status.HTTP_201_CREATED,
)
async def ingest_alert(
    tenant_id: UUID,
    payload: DetectionFindingIngest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ALERT, Action.CREATE))
    ],
) -> ApiResponse[AlertResponse]:
    _check(auth, tenant_id)
    alert, _was_duplicate = await alert_service.ingest_alert(db, tenant_id, payload)
    return ApiResponse(data=alert_service.alert_to_response(alert))


@router.get("/{alert_id}", response_model=ApiResponse[AlertResponse])
async def get_alert(
    tenant_id: UUID,
    alert_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ALERT, Action.READ))
    ],
) -> ApiResponse[AlertResponse]:
    _check(auth, tenant_id)
    alert = await alert_service._get_alert_or_404(db, alert_id)
    if alert.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    return ApiResponse(data=alert_service.alert_to_response(alert))


@router.post("/{alert_id}/dismiss", response_model=ApiResponse[AlertResponse])
async def dismiss_alert(
    tenant_id: UUID,
    alert_id: UUID,
    payload: AlertDismiss,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ALERT, Action.UPDATE))
    ],
) -> ApiResponse[AlertResponse]:
    _check(auth, tenant_id)
    alert = await alert_service.dismiss_alert(db, alert_id, payload)
    return ApiResponse(data=alert_service.alert_to_response(alert))


@router.post("/{alert_id}/promote", response_model=ApiResponse[CaseResponse])
async def promote_alert(
    tenant_id: UUID,
    alert_id: UUID,
    payload: AlertPromote,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ALERT, Action.UPDATE))
    ],
) -> ApiResponse[CaseResponse]:
    _check(auth, tenant_id)
    _alert, case = await alert_service.promote_alert(
        db, alert_id, payload, actor_id=auth.user_id
    )
    return ApiResponse(data=CaseResponse.model_validate(case))


__all__ = ["router"]

"""Timeline endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.timeline import (
    TimelineEntryCreate,
    TimelineEntryResponse,
    TimelineEntryUpdate,
    TimelineFilters,
    TimelineSwimlaneResponse,
)
from src.services import timeline as timeline_service

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/timeline", tags=["timeline"]
)


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


def _response_with_links(
    entry, linked_asset_ids: list[UUID]
) -> TimelineEntryResponse:
    data = TimelineEntryResponse.model_validate(entry).model_dump(by_alias=True)
    data["linked_asset_ids"] = linked_asset_ids
    return TimelineEntryResponse.model_validate(data)


@router.get("", response_model=ApiResponse[list[TimelineEntryResponse]])
async def list_timeline(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TIMELINE, Action.READ))
    ],
    event_type: str | None = None,
    category: str | None = None,
    actor_id: UUID | None = None,
    event_after: datetime | None = None,
    event_before: datetime | None = None,
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
) -> ApiResponse[list[TimelineEntryResponse]]:
    _check(auth, tenant_id)
    filters = TimelineFilters(
        event_type=event_type,
        category=category,
        actor_id=actor_id,
        event_after=event_after,
        event_before=event_before,
        order=order,
    )
    rows, total = await timeline_service.list_entries(
        db, case_id, filters, limit=pagination.page_size, offset=pagination.offset
    )
    links = await timeline_service.get_asset_links(db, [r.id for r in rows])
    responses = [_response_with_links(r, links.get(r.id, [])) for r in rows]
    return ApiResponse(
        data=responses,
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post(
    "",
    response_model=ApiResponse[TimelineEntryResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_manual_entry(
    tenant_id: UUID,
    case_id: UUID,
    payload: TimelineEntryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TIMELINE, Action.CREATE))
    ],
) -> ApiResponse[TimelineEntryResponse]:
    _check(auth, tenant_id)
    entry = await timeline_service.create_manual_entry(
        db, case_id=case_id, actor_id=auth.user_id, payload=payload
    )
    links = await timeline_service.get_asset_links(db, [entry.id])
    return ApiResponse(data=_response_with_links(entry, links.get(entry.id, [])))


@router.patch("/{entry_id}", response_model=ApiResponse[TimelineEntryResponse])
async def update_entry(
    tenant_id: UUID,
    case_id: UUID,
    entry_id: UUID,
    payload: TimelineEntryUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TIMELINE, Action.UPDATE))
    ],
) -> ApiResponse[TimelineEntryResponse]:
    _check(auth, tenant_id)
    entry = await timeline_service.update_entry(db, entry_id, payload)
    links = await timeline_service.get_asset_links(db, [entry.id])
    return ApiResponse(data=_response_with_links(entry, links.get(entry.id, [])))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    tenant_id: UUID,
    case_id: UUID,
    entry_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TIMELINE, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await timeline_service.delete_entry(db, entry_id)


@router.get("/swimlane", response_model=ApiResponse[TimelineSwimlaneResponse])
async def get_swimlane(
    tenant_id: UUID,
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TIMELINE, Action.READ))
    ],
    cluster_threshold_seconds: int = Query(default=300, ge=1),
) -> ApiResponse[TimelineSwimlaneResponse]:
    _check(auth, tenant_id)
    filters = TimelineFilters(order="asc")
    entries, clusters, lanes = await timeline_service.build_swimlane(
        db, case_id, filters, cluster_threshold_seconds=cluster_threshold_seconds
    )
    links = await timeline_service.get_asset_links(db, [e.id for e in entries])
    responses = [_response_with_links(e, links.get(e.id, [])) for e in entries]
    return ApiResponse(
        data=TimelineSwimlaneResponse(
            entries=responses, clusters=clusters, lanes=lanes
        )
    )


__all__ = ["router"]

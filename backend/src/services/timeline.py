"""Timeline service: manual entries, filtering, swimlane assembly."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, TimelineAssetLink, TimelineEntry
from src.schemas.timeline import (
    TemporalCluster,
    TimelineEntryCreate,
    TimelineEntryUpdate,
    TimelineFilters,
)

from .clustering import find_clusters


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found")
    return case


async def _get_entry_or_404(db: AsyncSession, entry_id: UUID) -> TimelineEntry:
    entry = (
        await db.execute(select(TimelineEntry).where(TimelineEntry.id == entry_id))
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Timeline entry {entry_id} not found")
    return entry


async def _replace_asset_links(
    db: AsyncSession, entry: TimelineEntry, asset_ids: list[UUID]
) -> None:
    # Drop existing links
    existing = (
        await db.execute(
            select(TimelineAssetLink).where(
                TimelineAssetLink.timeline_entry_id == entry.id
            )
        )
    ).scalars().all()
    for link in existing:
        await db.delete(link)
    for asset_id in asset_ids:
        db.add(
            TimelineAssetLink(
                timeline_entry_id=entry.id, asset_id=asset_id
            )
        )
    await db.flush()


async def create_manual_entry(
    db: AsyncSession,
    *,
    case_id: UUID,
    actor_id: UUID,
    payload: TimelineEntryCreate,
) -> TimelineEntry:
    case = await _get_case_or_404(db, case_id)
    entry = TimelineEntry(
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type=payload.event_type,
        event_timestamp=payload.event_timestamp,
        description=payload.description,
        category=payload.category,
        actor_id=actor_id,
        is_automatic=False,
        event_metadata=payload.metadata,
    )
    db.add(entry)
    await db.flush()
    if payload.linked_asset_ids:
        await _replace_asset_links(db, entry, list(payload.linked_asset_ids))
    await db.refresh(entry)
    return entry


async def update_entry(
    db: AsyncSession, entry_id: UUID, payload: TimelineEntryUpdate
) -> TimelineEntry:
    entry = await _get_entry_or_404(db, entry_id)
    data = payload.model_dump(exclude_unset=True)
    linked_asset_ids = data.pop("linked_asset_ids", None)
    for k, v in data.items():
        if k == "metadata":
            entry.event_metadata = v  # type: ignore[assignment]
        else:
            setattr(entry, k, v)
    if linked_asset_ids is not None:
        await _replace_asset_links(db, entry, list(linked_asset_ids))
    await db.flush()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, entry_id: UUID) -> None:
    entry = await _get_entry_or_404(db, entry_id)
    if entry.is_automatic:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Automatic timeline entries cannot be deleted"
        )
    await db.delete(entry)
    await db.flush()


async def list_entries(
    db: AsyncSession,
    case_id: UUID,
    filters: TimelineFilters,
    *,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[TimelineEntry], int]:
    query = select(TimelineEntry).where(TimelineEntry.case_id == case_id)
    if filters.event_type:
        query = query.where(TimelineEntry.event_type == filters.event_type)
    if filters.category:
        query = query.where(TimelineEntry.category == filters.category)
    if filters.actor_id:
        query = query.where(TimelineEntry.actor_id == filters.actor_id)
    if filters.event_after:
        query = query.where(TimelineEntry.event_timestamp >= filters.event_after)
    if filters.event_before:
        query = query.where(TimelineEntry.event_timestamp <= filters.event_before)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    order = (
        TimelineEntry.event_timestamp.asc()
        if filters.order == "asc"
        else TimelineEntry.event_timestamp.desc()
    )
    rows = (
        await db.execute(query.order_by(order).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)


async def get_asset_links(
    db: AsyncSession, entry_ids: list[UUID]
) -> dict[UUID, list[UUID]]:
    if not entry_ids:
        return {}
    rows = (
        await db.execute(
            select(TimelineAssetLink).where(
                TimelineAssetLink.timeline_entry_id.in_(entry_ids)
            )
        )
    ).scalars().all()
    result: dict[UUID, list[UUID]] = defaultdict(list)
    for row in rows:
        result[row.timeline_entry_id].append(row.asset_id)
    return dict(result)


async def build_swimlane(
    db: AsyncSession,
    case_id: UUID,
    filters: TimelineFilters,
    *,
    cluster_threshold_seconds: int = 300,
) -> tuple[list[TimelineEntry], list[TemporalCluster], dict[str, list[UUID]]]:
    """Assemble swimlane data: entries, clusters, lane assignments."""
    entries, _ = await list_entries(db, case_id, filters, limit=2000)
    asset_links = await get_asset_links(db, [e.id for e in entries])

    # Lanes: prefer asset id, fallback to actor id, fallback to event category
    lanes: dict[str, list[UUID]] = defaultdict(list)
    for e in entries:
        linked = asset_links.get(e.id)
        if linked:
            for aid in linked:
                lanes[f"asset:{aid}"].append(e.id)
        elif e.actor_id is not None:
            lanes[f"user:{e.actor_id}"].append(e.id)
        else:
            lanes[f"category:{e.category or 'other'}"].append(e.id)

    clusters_raw = find_clusters(
        [e for e in entries], threshold_seconds=cluster_threshold_seconds
    )
    clusters = [
        TemporalCluster(
            start=c.start, end=c.end, entry_ids=list(c.entry_ids)
        )
        for c in clusters_raw
    ]
    return entries, clusters, dict(lanes)


__all__ = [
    "create_manual_entry",
    "update_entry",
    "delete_entry",
    "list_entries",
    "get_asset_links",
    "build_swimlane",
]

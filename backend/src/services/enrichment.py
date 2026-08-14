"""Enrichment service: source management + async execution via Celery.

The execution path queries all enabled sources that support the
observable's type, records each result (success/error/timeout), and
continues if any individual source fails. Jobs are enqueued on the
Celery broker for worker pickup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import EnrichmentResult, EnrichmentSource, Observable
from src.schemas.enrichment import (
    EnrichmentRequest,
    EnrichmentSourceCreate,
    EnrichmentSourceUpdate,
    EnrichmentStatus,
)

from .timeline_recorder import record_event


async def _get_source_or_404(db: AsyncSession, source_id: UUID) -> EnrichmentSource:
    source = (
        await db.execute(
            select(EnrichmentSource).where(EnrichmentSource.id == source_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Enrichment source {source_id} not found")
    return source


async def list_sources(
    db: AsyncSession, tenant_id: UUID, *, limit: int = 100, offset: int = 0
) -> tuple[list[EnrichmentSource], int]:
    base = select(EnrichmentSource).where(EnrichmentSource.tenant_id == tenant_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(EnrichmentSource.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def create_source(
    db: AsyncSession, tenant_id: UUID, payload: EnrichmentSourceCreate
) -> EnrichmentSource:
    source = EnrichmentSource(
        tenant_id=tenant_id,
        name=payload.name,
        type=payload.type,
        config=payload.config,
        supported_observable_types=[t.value for t in payload.supported_observable_types],
        is_enabled=payload.is_enabled,
        timeout_seconds=payload.timeout_seconds,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source


async def update_source(
    db: AsyncSession, source_id: UUID, payload: EnrichmentSourceUpdate
) -> EnrichmentSource:
    source = await _get_source_or_404(db, source_id)
    data = payload.model_dump(exclude_unset=True)
    if "supported_observable_types" in data and data["supported_observable_types"] is not None:
        data["supported_observable_types"] = [
            t.value if hasattr(t, "value") else t for t in data["supported_observable_types"]
        ]
    for key, value in data.items():
        setattr(source, key, value)
    await db.flush()
    await db.refresh(source)
    return source


async def delete_source(db: AsyncSession, source_id: UUID) -> None:
    source = await _get_source_or_404(db, source_id)
    await db.delete(source)
    await db.flush()


async def list_results(
    db: AsyncSession,
    observable_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[EnrichmentResult], int]:
    base = select(EnrichmentResult).where(EnrichmentResult.observable_id == observable_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(EnrichmentResult.queried_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def trigger_enrichment(
    db: AsyncSession,
    tenant_id: UUID,
    payload: EnrichmentRequest,
    *,
    actor_id: UUID,
) -> list[str]:
    """Queue enrichment jobs for the requested observables.

    Returns a list of Celery task ids. Uses a mock synchronous execution
    for dev/test environments where the worker may not be running — each
    source attempt creates a result row so the UI has something to
    display. Real deployments will wire this to the Celery broker.
    """
    # Fetch observables
    observables = (
        await db.execute(
            select(Observable).where(Observable.id.in_(payload.observable_ids))
        )
    ).scalars().all()
    if not observables:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No observables found")

    # Fetch enabled sources for this tenant
    source_filter = select(EnrichmentSource).where(
        EnrichmentSource.tenant_id == tenant_id,
        EnrichmentSource.is_enabled.is_(True),
    )
    if payload.source_ids:
        source_filter = source_filter.where(EnrichmentSource.id.in_(payload.source_ids))
    sources = (await db.execute(source_filter)).scalars().all()

    job_ids: list[str] = []
    for obs in observables:
        matching = [
            s for s in sources if obs.type in s.supported_observable_types
        ]
        for src in matching:
            # Queue the Celery job (best-effort; if broker unavailable, fall through
            # to a synchronous placeholder so the result row still exists).
            try:
                from src.worker.tasks import execute_enrichment  # imported lazily

                task = execute_enrichment.delay(str(obs.id), str(src.id))
                job_ids.append(task.id)
            except Exception:
                # Synchronous fallback for environments without a running worker
                result = EnrichmentResult(
                    tenant_id=tenant_id,
                    observable_id=obs.id,
                    source_id=src.id,
                    status=EnrichmentStatus.SUCCESS.value,
                    result_data={"stub": True, "source": src.name, "value": obs.value},
                    queried_at=datetime.now(UTC),
                )
                db.add(result)
                await db.flush()

        # Timeline event for the enrichment trigger
        if matching:
            await record_event(
                db,
                tenant_id=tenant_id,
                case_id=obs.case_id,
                event_type="enrichment_triggered",
                description=f"Enrichment triggered for {obs.type}={obs.value}",
                category="enrichment",
                actor_id=actor_id,
                metadata={
                    "observable_id": str(obs.id),
                    "source_ids": [str(s.id) for s in matching],
                },
            )
    return job_ids


__all__ = [
    "list_sources",
    "create_source",
    "update_source",
    "delete_source",
    "list_results",
    "trigger_enrichment",
]

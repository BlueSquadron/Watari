"""Case service layer.

Handles case creation (with `next_case_number`), status transitions,
assignment, merging, and template application. All mutations record
corresponding timeline entries via `timeline_recorder.record_event`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Observable, Task, TimelineEntry
from src.models.template import CaseTemplate
from src.schemas.cases import (
    CaseClose,
    CaseCreate,
    CaseListFilters,
    CaseMerge,
    CaseStatus,
    CaseUpdate,
)

from .timeline_recorder import record_event


async def _next_case_number(db: AsyncSession, tenant_id: UUID) -> int:
    """Allocate the next sequential case number for a tenant."""
    result = await db.execute(
        text("SELECT next_case_number(:tid)").bindparams(tid=str(tenant_id))
    )
    return int(result.scalar_one())


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (
        await db.execute(select(Case).where(Case.id == case_id))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return case


async def create_case(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    created_by: UUID,
    payload: CaseCreate,
) -> Case:
    """Create a new case, optionally applying a template."""
    case_number = await _next_case_number(db, tenant_id)

    tags = list(payload.tags)
    custom_fields = dict(payload.custom_fields)
    severity = payload.severity.value

    template: CaseTemplate | None = None
    if payload.template_id is not None:
        template = (
            await db.execute(
                select(CaseTemplate).where(CaseTemplate.id == payload.template_id)
            )
        ).scalar_one_or_none()
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {payload.template_id} not found",
            )
        # Apply template defaults: tags, custom fields, severity if not overridden
        template_tags = list(template.default_tags or [])
        tags = list({*tags, *template_tags})
        custom_fields = {**(template.custom_fields or {}), **custom_fields}
        if template.default_severity and payload.severity.value == "medium":
            severity = template.default_severity

    case = Case(
        tenant_id=tenant_id,
        case_number=case_number,
        title=payload.title,
        description=payload.description,
        severity=severity,
        status=CaseStatus.NEW.value,
        assignee_id=payload.assignee_id,
        template_id=payload.template_id,
        tags=tags,
        custom_fields=custom_fields,
        created_by=created_by,
    )
    db.add(case)
    await db.flush()

    # Timeline entry: case_created
    await record_event(
        db,
        tenant_id=tenant_id,
        case_id=case.id,
        event_type="case_created",
        description=f"Case created: {case.title}",
        category="lifecycle",
        actor_id=created_by,
    )

    # Apply template tasks
    if template is not None and template.tasks:
        for idx, spec in enumerate(template.tasks):
            if not isinstance(spec, dict):
                continue
            task = Task(
                tenant_id=tenant_id,
                case_id=case.id,
                title=spec.get("title", f"Task {idx + 1}"),
                description=spec.get("description"),
                sort_order=spec.get("sort_order", idx),
                created_by=created_by,
            )
            db.add(task)
        await db.flush()

    # Fire platform event for module hooks
    from src.modules.base import PlatformEvent
    from . import events

    await events.fire(
        db,
        tenant_id=tenant_id,
        event=PlatformEvent.CASE_CREATED,
        payload={"case_id": str(case.id), "title": case.title, "severity": case.severity},
        actor_id=created_by,
    )

    await db.refresh(case)
    return case


async def list_cases(
    db: AsyncSession,
    tenant_id: UUID,
    filters: CaseListFilters,
    *,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Case], int]:
    """List cases within a tenant with filters and pagination."""
    query = select(Case).where(Case.tenant_id == tenant_id)
    if filters.status is not None:
        query = query.where(Case.status == filters.status.value)
    if filters.severity is not None:
        query = query.where(Case.severity == filters.severity.value)
    if filters.assignee_id is not None:
        query = query.where(Case.assignee_id == filters.assignee_id)
    if filters.tag is not None:
        query = query.where(Case.tags.contains([filters.tag]))  # type: ignore[attr-defined]
    if filters.created_after is not None:
        query = query.where(Case.created_at >= filters.created_after)
    if filters.created_before is not None:
        query = query.where(Case.created_at <= filters.created_before)
    if filters.search is not None and filters.search.strip():
        pattern = f"%{filters.search.strip()}%"
        query = query.where(
            (Case.title.ilike(pattern)) | (Case.description.ilike(pattern))
        )

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar_one()

    rows = (
        await db.execute(
            query.order_by(Case.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def get_case(db: AsyncSession, case_id: UUID) -> Case:
    return await _get_case_or_404(db, case_id)


async def update_case(
    db: AsyncSession,
    case_id: UUID,
    payload: CaseUpdate,
    *,
    actor_id: UUID,
) -> Case:
    """Update a case. Status changes and assignment changes record timeline events."""
    case = await _get_case_or_404(db, case_id)
    data = payload.model_dump(exclude_unset=True)

    old_status = case.status
    old_assignee = case.assignee_id

    for key, value in data.items():
        # Enum-style fields
        if key in {"status", "severity", "outcome"} and value is not None:
            setattr(case, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(case, key, value)

    # Status transition side effects
    if "status" in data and data["status"] is not None:
        new_status = case.status
        if new_status != old_status:
            now = datetime.now(UTC)
            if new_status == CaseStatus.RESOLVED.value:
                case.resolved_at = now
            if new_status == CaseStatus.CLOSED.value:
                if case.outcome is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Outcome is required when closing a case",
                    )
                case.closed_at = now
            await record_event(
                db,
                tenant_id=case.tenant_id,
                case_id=case.id,
                event_type="status_changed",
                description=f"Status changed from {old_status} to {new_status}",
                category="lifecycle",
                actor_id=actor_id,
                metadata={"from": old_status, "to": new_status},
            )

            # Dispatch platform event for modules
            from src.modules.base import PlatformEvent
            from . import events as _events

            await _events.fire(
                db,
                tenant_id=case.tenant_id,
                event=PlatformEvent.CASE_STATUS_CHANGED,
                payload={
                    "case_id": str(case.id),
                    "from": old_status,
                    "to": new_status,
                },
                actor_id=actor_id,
            )

    if "assignee_id" in data and data["assignee_id"] != old_assignee:
        await record_event(
            db,
            tenant_id=case.tenant_id,
            case_id=case.id,
            event_type="assignee_changed",
            description=(
                f"Assignee changed from {old_assignee} to {case.assignee_id}"
            ),
            category="lifecycle",
            actor_id=actor_id,
            metadata={"from": str(old_assignee) if old_assignee else None,
                      "to": str(case.assignee_id) if case.assignee_id else None},
        )

    await db.flush()
    await db.refresh(case)
    return case


async def close_case(
    db: AsyncSession, case_id: UUID, payload: CaseClose, *, actor_id: UUID
) -> Case:
    """Close a case with an outcome classification. Records a timeline event."""
    return await update_case(
        db,
        case_id,
        CaseUpdate(status=CaseStatus.CLOSED, outcome=payload.outcome),
        actor_id=actor_id,
    )


async def merge_cases(
    db: AsyncSession,
    target_case_id: UUID,
    payload: CaseMerge,
    *,
    actor_id: UUID,
) -> Case:
    """Merge N source cases into a single target case.

    Transfers all observables and timeline entries from sources to target,
    records merged_from on the target, and records a merge event.
    """
    target = await _get_case_or_404(db, target_case_id)

    sources: list[Case] = []
    for source_id in payload.source_case_ids:
        if source_id == target_case_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge a case into itself",
            )
        src = await _get_case_or_404(db, source_id)
        if src.tenant_id != target.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot merge across tenants",
            )
        sources.append(src)

    # Transfer observables
    for src in sources:
        await db.execute(
            select(Observable)
            .where(Observable.case_id == src.id)
            .execution_options(synchronize_session=False)
        )
        observables = (
            await db.execute(
                select(Observable).where(Observable.case_id == src.id)
            )
        ).scalars().all()
        for obs in observables:
            obs.case_id = target.id

        # Transfer timeline entries
        entries = (
            await db.execute(
                select(TimelineEntry).where(TimelineEntry.case_id == src.id)
            )
        ).scalars().all()
        for entry in entries:
            entry.case_id = target.id

    # Record merged_from
    existing = list(target.merged_from or [])
    existing.extend([s.id for s in sources])
    target.merged_from = existing

    await record_event(
        db,
        tenant_id=target.tenant_id,
        case_id=target.id,
        event_type="cases_merged",
        description=f"Merged {len(sources)} case(s) into this one",
        category="lifecycle",
        actor_id=actor_id,
        metadata={"source_case_ids": [str(s.id) for s in sources]},
    )

    # Close source cases
    for src in sources:
        src.status = CaseStatus.CLOSED.value
        src.closed_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(target)
    return target


async def delete_case(db: AsyncSession, case_id: UUID) -> None:
    case = await _get_case_or_404(db, case_id)
    await db.delete(case)
    await db.flush()


__all__ = [
    "create_case",
    "list_cases",
    "get_case",
    "update_case",
    "close_case",
    "merge_cases",
    "delete_case",
]

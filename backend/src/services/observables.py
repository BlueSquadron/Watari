"""Observable service layer with format validation and cross-case correlation."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Observable
from src.schemas.observables import (
    ObservableBulkCreate,
    ObservableCreate,
    ObservableType,
    ObservableUpdate,
)

from .timeline_recorder import record_event
from .validators import validate_observable


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return case


async def _get_observable_or_404(db: AsyncSession, observable_id: UUID) -> Observable:
    obs = (
        await db.execute(select(Observable).where(Observable.id == observable_id))
    ).scalar_one_or_none()
    if obs is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Observable {observable_id} not found",
        )
    return obs


def _normalize_or_400(type: ObservableType, value: str) -> str:
    try:
        return validate_observable(type, value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {type} observable: {exc}",
        ) from exc


async def create_observable(
    db: AsyncSession,
    *,
    case_id: UUID,
    created_by: UUID,
    payload: ObservableCreate,
) -> Observable:
    case = await _get_case_or_404(db, case_id)
    normalized = _normalize_or_400(payload.type, payload.value)
    obs = Observable(
        tenant_id=case.tenant_id,
        case_id=case.id,
        type=payload.type.value,
        value=normalized,
        tlp=payload.tlp.value if payload.tlp else None,
        is_ioc=payload.is_ioc,
        tags=list(payload.tags),
        description=payload.description,
        created_by=created_by,
    )
    db.add(obs)
    await db.flush()
    await record_event(
        db,
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type="observable_added",
        description=f"Observable added: {obs.type}={obs.value}",
        category="observable",
        actor_id=created_by,
        metadata={"observable_id": str(obs.id), "type": obs.type, "value": obs.value},
    )
    # Dispatch platform event for modules
    from src.modules.base import PlatformEvent

    from . import events as _events

    await _events.fire(
        db,
        tenant_id=case.tenant_id,
        event=PlatformEvent.OBSERVABLE_CREATED,
        payload={
            "case_id": str(case.id),
            "observable_id": str(obs.id),
            "type": obs.type,
            "value": obs.value,
        },
        actor_id=created_by,
    )
    await db.refresh(obs)
    return obs


async def create_observables_bulk(
    db: AsyncSession,
    *,
    case_id: UUID,
    created_by: UUID,
    payload: ObservableBulkCreate,
) -> list[Observable]:
    created: list[Observable] = []
    for item in payload.observables:
        created.append(
            await create_observable(db, case_id=case_id, created_by=created_by, payload=item)
        )
    return created


async def list_observables(
    db: AsyncSession,
    case_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Observable], int]:
    base = select(Observable).where(Observable.case_id == case_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (await db.execute(base.order_by(Observable.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def update_observable(
    db: AsyncSession,
    observable_id: UUID,
    payload: ObservableUpdate,
) -> Observable:
    obs = await _get_observable_or_404(db, observable_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "tlp" and value is not None:
            setattr(obs, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(obs, key, value)
    await db.flush()
    await db.refresh(obs)
    return obs


async def delete_observable(db: AsyncSession, observable_id: UUID) -> None:
    obs = await _get_observable_or_404(db, observable_id)
    await db.delete(obs)
    await db.flush()


async def cross_case_count(
    db: AsyncSession, tenant_id: UUID, type: str, value: str, exclude_case_id: UUID
) -> int:
    """Return number of OTHER cases in this tenant containing the same observable."""
    result = await db.execute(
        select(func.count(func.distinct(Observable.case_id)))
        .where(Observable.tenant_id == tenant_id)
        .where(Observable.type == type)
        .where(Observable.value == value)
        .where(Observable.case_id != exclude_case_id)
    )
    return int(result.scalar_one())


async def find_correlating_cases(
    db: AsyncSession, tenant_id: UUID, type: str, value: str
) -> list[UUID]:
    """Return all case ids within a tenant containing the given observable value."""
    rows = (
        (
            await db.execute(
                select(Observable.case_id)
                .where(Observable.tenant_id == tenant_id)
                .where(Observable.type == type)
                .where(Observable.value == value)
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


__all__ = [
    "create_observable",
    "create_observables_bulk",
    "list_observables",
    "update_observable",
    "delete_observable",
    "cross_case_count",
    "find_correlating_cases",
]

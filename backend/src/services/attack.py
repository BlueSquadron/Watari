"""MITRE ATT&CK mapping service.

Tags cases, observables, and timeline entries with tactic/technique IDs
and computes the tenant-scoped heatmap that drives the visualization.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AttackMapping, AttackReference, Case
from src.schemas.attack import (
    AttackHeatmapCell,
    AttackMappingCreate,
)


async def _get_mapping_or_404(db: AsyncSession, mapping_id: UUID) -> AttackMapping:
    m = (await db.execute(select(AttackMapping).where(AttackMapping.id == mapping_id))).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Mapping {mapping_id} not found")
    return m


async def create_mapping(
    db: AsyncSession, tenant_id: UUID, payload: AttackMappingCreate, *, created_by: UUID
) -> AttackMapping:
    if not any([payload.case_id, payload.observable_id, payload.timeline_entry_id]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "At least one of case_id, observable_id, or timeline_entry_id is required",
        )
    mapping = AttackMapping(
        tenant_id=tenant_id,
        case_id=payload.case_id,
        observable_id=payload.observable_id,
        timeline_entry_id=payload.timeline_entry_id,
        tactic_id=payload.tactic_id,
        technique_id=payload.technique_id,
        sub_technique_id=payload.sub_technique_id,
        created_by=created_by,
    )
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


async def delete_mapping(db: AsyncSession, mapping_id: UUID) -> None:
    mapping = await _get_mapping_or_404(db, mapping_id)
    await db.delete(mapping)
    await db.flush()


async def list_mappings_for_case(
    db: AsyncSession, case_id: UUID
) -> list[AttackMapping]:
    rows = (
        await db.execute(
            select(AttackMapping).where(AttackMapping.case_id == case_id)
        )
    ).scalars().all()
    return list(rows)


async def list_reference(db: AsyncSession) -> list[AttackReference]:
    rows = (
        await db.execute(select(AttackReference).order_by(AttackReference.technique_id))
    ).scalars().all()
    return list(rows)


_SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "informational": 0,
}


async def build_heatmap(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    case_severity: str | None = None,
    case_status: str | None = None,
) -> list[AttackHeatmapCell]:
    """Compute frequency + max severity per (tactic, technique) for the tenant."""
    # Join via case_id when present so we can filter by case attributes
    q = (
        select(
            AttackMapping.tactic_id,
            AttackMapping.technique_id,
            AttackMapping.case_id,
            Case.severity,
            Case.status,
        )
        .outerjoin(Case, Case.id == AttackMapping.case_id)
        .where(AttackMapping.tenant_id == tenant_id)
    )
    if created_after:
        q = q.where(AttackMapping.created_at >= created_after)
    if created_before:
        q = q.where(AttackMapping.created_at <= created_before)
    if case_severity:
        q = q.where(Case.severity == case_severity)
    if case_status:
        q = q.where(Case.status == case_status)

    rows = (await db.execute(q)).all()

    # Aggregate
    cells: dict[tuple[str, str], dict] = {}
    for tactic_id, technique_id, case_id, severity, _status in rows:
        key = (tactic_id, technique_id)
        cell = cells.setdefault(
            key,
            {
                "case_ids": set(),
                "severities": set(),
            },
        )
        if case_id is not None:
            cell["case_ids"].add(case_id)
        if severity:
            cell["severities"].add(severity)

    result: list[AttackHeatmapCell] = []
    for (tactic_id, technique_id), data in cells.items():
        sevs = data["severities"]
        max_sev = None
        if sevs:
            max_sev = max(sevs, key=lambda s: _SEVERITY_RANK.get(s, -1))
        result.append(
            AttackHeatmapCell(
                tactic_id=tactic_id,
                technique_id=technique_id,
                case_count=len(data["case_ids"]),
                max_severity=max_sev,
                linked_case_ids=sorted(data["case_ids"]),
            )
        )
    result.sort(key=lambda c: (c.tactic_id, c.technique_id))
    return result


def compute_heatmap_cells(
    mappings: list[tuple[str, str, UUID | None, str | None]],
) -> list[AttackHeatmapCell]:
    """Pure helper: compute cells from a list of (tactic, technique, case_id, severity).

    Used by the property test (27) to verify aggregation without a database.
    """
    cells: dict[tuple[str, str], dict] = {}
    for tactic, technique, case_id, severity in mappings:
        cell = cells.setdefault((tactic, technique), {"case_ids": set(), "severities": set()})
        if case_id is not None:
            cell["case_ids"].add(case_id)
        if severity:
            cell["severities"].add(severity)
    out: list[AttackHeatmapCell] = []
    for (tactic, technique), data in cells.items():
        max_sev = None
        if data["severities"]:
            max_sev = max(data["severities"], key=lambda s: _SEVERITY_RANK.get(s, -1))
        out.append(
            AttackHeatmapCell(
                tactic_id=tactic,
                technique_id=technique,
                case_count=len(data["case_ids"]),
                max_severity=max_sev,
                linked_case_ids=sorted(data["case_ids"]),
            )
        )
    out.sort(key=lambda c: (c.tactic_id, c.technique_id))
    return out


__all__ = [
    "create_mapping",
    "delete_mapping",
    "list_mappings_for_case",
    "list_reference",
    "build_heatmap",
    "compute_heatmap_cells",
]

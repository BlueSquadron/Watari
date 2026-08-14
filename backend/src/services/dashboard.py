"""Dashboard metrics service with Redis-backed caching.

All metrics are scoped to a tenant and optionally filtered by date range.
Cached results live in Redis for 60 seconds (configurable) to keep
dashboard responses under the 5-second target for typical tenant sizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, User
from src.schemas.dashboard import (
    AnalystWorkloadPoint,
    DashboardMetricsResponse,
    OutcomeCountPoint,
    SeverityCountPoint,
    StatusCountPoint,
    TimeSeriesPoint,
)

_CACHE_KEY = "dashboard:{tenant_id}:{fingerprint}"
_CACHE_TTL_SECONDS = 60


@dataclass(frozen=True, slots=True)
class DashboardFilters:
    created_after: datetime | None = None
    created_before: datetime | None = None

    def fingerprint(self) -> str:
        return (
            f"{self.created_after.isoformat() if self.created_after else 'none'}"
            f":{self.created_before.isoformat() if self.created_before else 'none'}"
        )


async def compute_metrics(
    db: AsyncSession, tenant_id: UUID, filters: DashboardFilters
) -> DashboardMetricsResponse:
    # Try cache first
    from src.utils import get_redis

    redis = get_redis()
    cache_key = _CACHE_KEY.format(tenant_id=tenant_id, fingerprint=filters.fingerprint())
    try:
        cached = await redis.get(cache_key)
        if cached:
            return DashboardMetricsResponse.model_validate_json(cached)
    except Exception:  # noqa: BLE001
        # Cache miss / redis unavailable — compute fresh
        pass

    base_where = [Case.tenant_id == tenant_id]
    if filters.created_after:
        base_where.append(Case.created_at >= filters.created_after)
    if filters.created_before:
        base_where.append(Case.created_at <= filters.created_before)

    # Open cases by severity
    severity_rows = (
        await db.execute(
            select(Case.severity, func.count(Case.id))
            .where(*base_where)
            .where(Case.status.in_(["new", "in_progress", "pending"]))
            .group_by(Case.severity)
        )
    ).all()
    open_by_severity = [SeverityCountPoint(severity=s, count=c) for s, c in severity_rows]

    # Cases by status
    status_rows = (
        await db.execute(
            select(Case.status, func.count(Case.id)).where(*base_where).group_by(Case.status)
        )
    ).all()
    by_status = [StatusCountPoint(status=s, count=c) for s, c in status_rows]

    # Cases by outcome (closed only)
    outcome_rows = (
        await db.execute(
            select(Case.outcome, func.count(Case.id))
            .where(*base_where)
            .where(Case.outcome.isnot(None))
            .group_by(Case.outcome)
        )
    ).all()
    by_outcome = [OutcomeCountPoint(outcome=o, count=c) for o, c in outcome_rows if o]

    # Mean time to resolution (hours) — closed cases in the filter window
    mttr_row = (
        await db.execute(
            select(func.avg(func.extract("epoch", Case.resolved_at - Case.created_at)))
            .where(*base_where)
            .where(Case.resolved_at.isnot(None))
        )
    ).scalar_one_or_none()
    mttr_hours = None
    if mttr_row is not None:
        try:
            mttr_hours = float(mttr_row) / 3600.0
        except (TypeError, ValueError):
            mttr_hours = None

    # Cases created over time — bucketed by day
    created_rows = (
        await db.execute(
            select(
                func.date_trunc("day", Case.created_at).label("day"),
                func.count(Case.id),
            )
            .where(*base_where)
            .group_by("day")
            .order_by("day")
        )
    ).all()
    created_series = [TimeSeriesPoint(timestamp=d, value=float(c)) for d, c in created_rows]

    # Analyst workload: open cases per assignee + resolved cases in last 7d
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    workload_rows = (
        await db.execute(
            select(
                User.id,
                User.display_name,
                func.count(Case.id).filter(Case.status.in_(["new", "in_progress", "pending"])),
                func.count(Case.id).filter(
                    Case.resolved_at.isnot(None),
                    Case.resolved_at >= seven_days_ago,
                ),
            )
            .join(Case, Case.assignee_id == User.id, isouter=True)
            .where(User.tenant_id == tenant_id)
            .where(User.is_active.is_(True))
            .group_by(User.id, User.display_name)
        )
    ).all()
    workload = [
        AnalystWorkloadPoint(
            analyst_id=str(uid),
            analyst_name=name,
            open_cases=int(open_count or 0),
            resolved_cases_7d=int(resolved_count or 0),
        )
        for uid, name, open_count, resolved_count in workload_rows
    ]

    response = DashboardMetricsResponse(
        open_cases_by_severity=open_by_severity,
        cases_by_status=by_status,
        cases_by_outcome=by_outcome,
        mean_time_to_resolution_hours=mttr_hours,
        cases_created_over_time=created_series,
        analyst_workload=workload,
    )

    # Cache the result
    try:
        await redis.setex(
            cache_key,
            _CACHE_TTL_SECONDS,
            response.model_dump_json(),
        )
    except Exception:  # noqa: BLE001
        pass

    return response


__all__ = ["DashboardFilters", "compute_metrics"]

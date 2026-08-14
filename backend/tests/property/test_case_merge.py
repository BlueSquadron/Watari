"""Property 5: Case Merge Data Preservation.

For any set of cases being merged into a target case, ALL observables and
ALL timeline entries from every source case SHALL appear in the merged
target case.

Feature: watari-case-management, Property 5: Case Merge Data Preservation
**Validates: Requirements 3.8**

Requires a live PostgreSQL database with migrations applied.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Observable, TimelineEntry
from src.schemas.cases import CaseCreate, CaseMerge, CaseSeverity
from src.schemas.observables import ObservableCreate, ObservableType
from src.services import cases as case_service
from src.services import observables as observable_service
from src.services.timeline_recorder import record_event

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


@pytest.mark.asyncio
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    deadline=None,
)
@given(
    obs_counts=st.lists(st.integers(min_value=0, max_value=3), min_size=2, max_size=4),
    tl_counts=st.lists(st.integers(min_value=0, max_value=3), min_size=2, max_size=4),
)
async def test_merge_preserves_observables_and_timeline(
    obs_counts: list[int],
    tl_counts: list[int],
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Merging N sources into a target preserves all observables and timeline entries."""
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    # Create a target and N source cases
    target = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="Target", severity=CaseSeverity.MEDIUM, tags=[], custom_fields={}),
    )

    sources: list[Case] = []
    expected_obs_values: list[str] = []
    expected_tl_ids: list[UUID] = []
    n = min(len(obs_counts), len(tl_counts))
    obs_counts = obs_counts[:n]
    tl_counts = tl_counts[:n]

    for i, (oc, tc) in enumerate(zip(obs_counts, tl_counts, strict=False)):
        src = await case_service.create_case(
            db_session,
            tenant_id=tenant.id,
            created_by=user.id,
            payload=CaseCreate(
                title=f"Src {i}",
                severity=CaseSeverity.LOW,
                tags=[],
                custom_fields={},
            ),
        )
        sources.append(src)
        # Add observables — use distinct values so assertions are unambiguous
        for j in range(oc):
            value = f"10.{i}.{j}.1"
            await observable_service.create_observable(
                db_session,
                case_id=src.id,
                created_by=user.id,
                payload=ObservableCreate(type=ObservableType.IP, value=value),
            )
            expected_obs_values.append(value)
        # Add manual timeline entries
        for j in range(tc):
            entry = await record_event(
                db_session,
                tenant_id=tenant.id,
                case_id=src.id,
                event_type="manual",
                description=f"manual entry {i}.{j}",
                event_timestamp=datetime(2025, 1, 1, 12, i, j, tzinfo=UTC),
            )
            expected_tl_ids.append(entry.id)

    # Perform the merge
    await case_service.merge_cases(
        db_session,
        target.id,
        CaseMerge(source_case_ids=[s.id for s in sources]),
        actor_id=user.id,
    )

    # All observables from sources must now live on the target
    merged_observables = (
        (await db_session.execute(select(Observable.value).where(Observable.case_id == target.id)))
        .scalars()
        .all()
    )
    assert sorted(v for v in merged_observables if v in expected_obs_values) == sorted(
        expected_obs_values
    ), f"Expected {sorted(expected_obs_values)}, got {sorted(str(v) for v in merged_observables)}"

    # All timeline entries from sources must now live on the target
    merged_tl_ids = set(
        (
            await db_session.execute(
                select(TimelineEntry.id).where(TimelineEntry.case_id == target.id)
            )
        )
        .scalars()
        .all()
    )
    assert set(expected_tl_ids).issubset(merged_tl_ids), (
        f"Expected timeline entries {expected_tl_ids} to be on target, "
        f"but missing: {set(expected_tl_ids) - merged_tl_ids}"
    )

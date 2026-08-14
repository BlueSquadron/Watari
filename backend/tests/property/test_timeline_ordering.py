"""Property 9: Timeline Ordering and Completeness.

For any case timeline, entries SHALL be ordered by event_timestamp in the
requested direction (ascending or descending), and every entry SHALL
contain non-null values for timestamp, event type, and description.

Feature: watari-case-management, Property 9: Timeline Ordering and Completeness
**Validates: Requirements 8.1, 8.6**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.timeline import _response_with_links
from src.schemas.cases import CaseCreate, CaseSeverity
from src.schemas.timeline import TimelineEntryCreate, TimelineFilters
from src.services import cases as case_service
from src.services import timeline as timeline_service

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
    offsets=st.lists(st.integers(min_value=0, max_value=86400), min_size=1, max_size=8),
    order=st.sampled_from(["asc", "desc"]),
)
async def test_timeline_ordering_and_non_null_fields(
    offsets: list[int],
    order: str,
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )

    base = datetime(2025, 1, 1, tzinfo=UTC)
    for i, off in enumerate(offsets):
        await timeline_service.create_manual_entry(
            db_session,
            case_id=case.id,
            actor_id=user.id,
            payload=TimelineEntryCreate(
                event_type="manual",
                event_timestamp=base + timedelta(seconds=off),
                description=f"event {i}",
            ),
        )

    entries, _ = await timeline_service.list_entries(
        db_session, case.id, TimelineFilters(order=order), limit=500
    )

    # Ordering invariant
    times = [e.event_timestamp for e in entries]
    assert times == (sorted(times) if order == "asc" else sorted(times, reverse=True))
    # Non-null invariants
    for e in entries:
        assert e.event_timestamp is not None
        assert e.event_type
        assert e.description


@pytest.mark.asyncio
async def test_timeline_response_exposes_metadata_as_a_dict(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Regression for #1.

    `TimelineEntryResponse` serializes its `event_metadata` field under the
    public name `metadata`. Validating that alias against a SQLAlchemy model
    resolves `Base.metadata` — the declarative `MetaData` registry — instead of
    the JSONB column, which made every timeline request 500.
    """
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )
    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    entry = await timeline_service.create_manual_entry(
        db_session,
        case_id=case.id,
        actor_id=user.id,
        payload=TimelineEntryCreate(
            event_type="manual",
            event_timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            description="metadata round trip",
            metadata={"source": "regression-test"},
        ),
    )

    response = _response_with_links(entry, [])
    assert response.event_metadata == {"source": "regression-test"}

    # The wire format must keep the `metadata` key — this is a public response
    # shape, so the fix must not rename the field.
    dumped = response.model_dump(by_alias=True)
    assert dumped["metadata"] == {"source": "regression-test"}
    assert "event_metadata" not in dumped

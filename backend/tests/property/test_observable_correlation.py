"""Property 7: Observable Cross-Case Correlation.

For any observable value within a tenant, querying for cases containing
that observable SHALL return exactly the set of cases where an
observable with that value exists.

Feature: watari-case-management, Property 7: Observable Cross-Case Correlation
**Validates: Requirements 6.5, 11.4, 19.3**
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.cases import CaseCreate, CaseSeverity
from src.schemas.observables import ObservableCreate, ObservableType
from src.services import cases as case_service
from src.services import observables as observable_service

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
    case_has_observable=st.lists(
        st.booleans(), min_size=3, max_size=6
    ),
)
async def test_correlating_cases_match_exactly(
    case_has_observable: list[bool],
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    target_value = "203.0.113.42"
    expected_case_ids = set()

    for i, has_obs in enumerate(case_has_observable):
        case = await case_service.create_case(
            db_session,
            tenant_id=tenant.id,
            created_by=user.id,
            payload=CaseCreate(
                title=f"Case {i}", severity=CaseSeverity.LOW, tags=[], custom_fields={}
            ),
        )
        if has_obs:
            await observable_service.create_observable(
                db_session,
                case_id=case.id,
                created_by=user.id,
                payload=ObservableCreate(
                    type=ObservableType.IP, value=target_value
                ),
            )
            expected_case_ids.add(case.id)
        # Always add a distinct observable so every case has something
        await observable_service.create_observable(
            db_session,
            case_id=case.id,
            created_by=user.id,
            payload=ObservableCreate(
                type=ObservableType.IP, value=f"10.0.0.{i + 1}"
            ),
        )

    actual_case_ids = set(
        await observable_service.find_correlating_cases(
            db_session, tenant.id, ObservableType.IP.value, target_value
        )
    )
    assert actual_case_ids == expected_case_ids

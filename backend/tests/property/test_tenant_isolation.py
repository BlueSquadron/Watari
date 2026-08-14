"""Property 1: Tenant Data Isolation.

For any user authenticated within a tenant context, and for any query
executed against any tenant-scoped table, the results SHALL contain only
rows where `tenant_id` matches the user's current tenant.

Feature: watari-case-management, Property 1: Tenant Data Isolation
**Validates: Requirements 1.2, 1.3, 15.2**

Note: These tests require a live PostgreSQL instance because Row-Level
Security policies cannot be exercised without one. Set
`TEST_DATABASE_URL` or `DATABASE_URL` to run them locally or in CI.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database; set TEST_DATABASE_URL or DATABASE_URL",
)

async def _enforce_rls(db_session: AsyncSession) -> None:
    """Drop the platform-admin bypass that `db_session` sets by default.

    Without this the tests below would pass vacuously, which is exactly how
    the original RLS bug hid for so long.
    """
    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'false'"))


async def _allow_setup(db_session: AsyncSession) -> None:
    """Restore the bypass so a test can build its fixtures.

    Hypothesis re-runs the test body many times against the same session, so
    a test that switches enforcement on must switch it back before the next
    example tries to insert.
    """
    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))


@pytest.mark.asyncio
@settings(
    max_examples=20,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    deadline=None,
)
@given(
    case_counts=st.lists(
        st.integers(min_value=1, max_value=5),
        min_size=2,
        max_size=4,
    )
)
async def test_rls_isolates_tenants_on_select(
    case_counts: list[int],
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """RLS policies prevent queries from returning rows from other tenants."""
    await _allow_setup(db_session)

    tenants: list[tuple[object, int]] = []
    for i, count in enumerate(case_counts):
        tenant = await tenant_factory(name=f"Tenant {i}")
        user = await user_factory(tenant.id, role="analyst")
        for j in range(count):
            case = Case(
                tenant_id=tenant.id,
                case_number=j + 1,
                title=f"Case {j} of tenant {i}",
                severity="medium",
                created_by=user.id,
            )
            db_session.add(case)
        await db_session.flush()
        tenants.append((tenant, count))

    # Setup is done; from here the session is an ordinary tenant user.
    await _enforce_rls(db_session)

    # For each tenant context the SELECT must return only that tenant's cases
    for tenant, expected_count in tenants:
        await db_session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(
                tid=str(tenant.id)
            )
        )
        result = await db_session.execute(select(Case))
        rows = result.scalars().all()

        assert all(row.tenant_id == tenant.id for row in rows), (
            f"RLS failed: a row in tenant {tenant.id}'s context had a different tenant_id"
        )
        assert len(rows) == expected_count, (
            f"Expected {expected_count} rows for tenant {tenant.id}, got {len(rows)}"
        )


@pytest.mark.asyncio
async def test_rls_denies_cross_tenant_access(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """A query in tenant A's context must not see tenant B's rows."""
    tenant_a = await tenant_factory(name="A")
    tenant_b = await tenant_factory(name="B")
    user_a = await user_factory(tenant_a.id)
    user_b = await user_factory(tenant_b.id)

    db_session.add(
        Case(
            tenant_id=tenant_a.id,
            case_number=1,
            title="A1",
            severity="low",
            created_by=user_a.id,
        )
    )
    db_session.add(
        Case(
            tenant_id=tenant_b.id,
            case_number=1,
            title="B1",
            severity="low",
            created_by=user_b.id,
        )
    )
    await db_session.flush()

    # Setup is done; from here the session is an ordinary tenant user.
    await _enforce_rls(db_session)

    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant_a.id))
    )
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert [r.title for r in rows] == ["A1"]

    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant_b.id))
    )
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert [r.title for r in rows] == ["B1"]


@pytest.mark.asyncio
async def test_platform_admin_bypass_sees_all(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Platform admin bypass policy returns rows across tenants.

    Asserts both directions, because "sees everything" is also what a broken
    RLS setup looks like: with the bypass off and a tenant in context, the
    same query must narrow to that tenant.
    """
    tenant_a = await tenant_factory(name="A")
    tenant_b = await tenant_factory(name="B")
    user_a = await user_factory(tenant_a.id)
    user_b = await user_factory(tenant_b.id)

    db_session.add(
        Case(
            tenant_id=tenant_a.id,
            case_number=1,
            title="A1",
            severity="low",
            created_by=user_a.id,
        )
    )
    db_session.add(
        Case(
            tenant_id=tenant_b.id,
            case_number=1,
            title="B1",
            severity="low",
            created_by=user_b.id,
        )
    )
    await db_session.flush()

    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert sorted(r.title for r in rows) == ["A1", "B1"]

    # ...and the same query, without the bypass, must not.
    await _enforce_rls(db_session)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(
            tid=str(tenant_a.id)
        )
    )
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert [r.title for r in rows] == ["A1"]


@pytest.mark.asyncio
async def test_session_without_tenant_context_sees_nothing(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """RLS fails closed.

    A session that is neither a platform admin nor scoped to a tenant must
    return no rows at all — not every row. This is the property that decides
    whether a missing tenant context is an outage or a data leak, and it is
    why `get_db` may hand out an unscoped session safely.
    """
    tenant = await tenant_factory(name="A")
    user = await user_factory(tenant.id)
    db_session.add(
        Case(
            tenant_id=tenant.id,
            case_number=1,
            title="A1",
            severity="low",
            created_by=user.id,
        )
    )
    await db_session.flush()

    # No tenant ever set on this transaction, and no bypass.
    await _enforce_rls(db_session)

    rows = (await db_session.execute(select(Case))).scalars().all()
    assert rows == []

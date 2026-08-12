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

    # For each tenant context the SELECT must return only that tenant's cases
    for tenant, expected_count in tenants:
        await db_session.execute(
            text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
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

    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant_a.id))
    )
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert [r.title for r in rows] == ["A1"]

    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant_b.id))
    )
    rows = (await db_session.execute(select(Case))).scalars().all()
    assert [r.title for r in rows] == ["B1"]


@pytest.mark.asyncio
async def test_platform_admin_bypass_sees_all(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Platform admin bypass policy returns rows across tenants."""
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

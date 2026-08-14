"""Property 19: Sequential Case Number Assignment.

For any sequence of case creations within a single tenant, case numbers
SHALL be assigned sequentially starting from 1, with no gaps and no
duplicates.

Feature: watari-case-management, Property 19: Sequential Case Number Assignment
**Validates: Requirements 3.2**

Note: These tests require a live PostgreSQL instance because the
`next_case_number` PL/pgSQL function and RLS policies cannot be exercised
without one. Set `TEST_DATABASE_URL` or `DATABASE_URL` to run them locally
or in CI.
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database; set TEST_DATABASE_URL or DATABASE_URL",
)


@pytest.mark.asyncio
@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    deadline=None,
)
@given(n=st.integers(min_value=1, max_value=20))
async def test_case_numbers_are_sequential(
    n: int,
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Creating N cases in one tenant produces numbers 1..N with no gaps or duplicates."""
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)

    # Set tenant context so RLS does not hide rows when we read them back.
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    for _ in range(n):
        next_num = (
            await db_session.execute(
                text("SELECT next_case_number(CAST(:tid AS uuid))").bindparams(tid=str(tenant.id))
            )
        ).scalar_one()
        case = Case(
            tenant_id=tenant.id,
            case_number=next_num,
            title=f"Case {next_num}",
            severity="medium",
            created_by=user.id,
        )
        db_session.add(case)
        await db_session.flush()

    # Scope the read-back explicitly. This property is about numbering, not
    # isolation, and the fixture's connection may see other tenants' rows.
    rows = (
        (
            await db_session.execute(
                select(Case.case_number)
                .where(Case.tenant_id == tenant.id)
                .order_by(Case.case_number)
            )
        )
        .scalars()
        .all()
    )
    expected = list(range(1, n + 1))
    assert list(rows) == expected, f"Expected sequential 1..{n}, got {list(rows)}"


@pytest.mark.asyncio
async def test_case_numbers_are_per_tenant(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Case numbers restart at 1 for each tenant independently."""
    tenant_1 = await tenant_factory(name="T1")
    tenant_2 = await tenant_factory(name="T2")
    user_1 = await user_factory(tenant_1.id)
    user_2 = await user_factory(tenant_2.id)

    for tenant, user in [(tenant_1, user_1), (tenant_2, user_2)]:
        for _ in range(3):
            next_num = (
                await db_session.execute(
                    text("SELECT next_case_number(CAST(:tid AS uuid))").bindparams(
                        tid=str(tenant.id)
                    )
                )
            ).scalar_one()
            db_session.add(
                Case(
                    tenant_id=tenant.id,
                    case_number=next_num,
                    title=f"C{next_num}",
                    severity="low",
                    created_by=user.id,
                )
            )
            await db_session.flush()

    # Scope each read-back explicitly — this property is about per-tenant
    # numbering, not about isolation (see test_tenant_isolation.py for that).
    rows_1 = sorted(
        (await db_session.execute(select(Case.case_number).where(Case.tenant_id == tenant_1.id)))
        .scalars()
        .all()
    )
    rows_2 = sorted(
        (await db_session.execute(select(Case.case_number).where(Case.tenant_id == tenant_2.id)))
        .scalars()
        .all()
    )

    assert rows_1 == [1, 2, 3]
    assert rows_2 == [1, 2, 3]

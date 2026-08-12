"""Property 20: Asset Name Uniqueness Within Case.

For any case, no two assets SHALL have the same name. Attempting to add
an asset with a name that already exists within the case SHALL be
rejected with a validation error.

Feature: watari-case-management, Property 20: Asset Name Uniqueness Within Case
**Validates: Requirements 16.4**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.assets import AssetCreate, AssetType
from src.schemas.cases import CaseCreate, CaseSeverity
from src.services import assets as asset_service
from src.services import cases as case_service

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
    name=st.text(
        alphabet="abcdefghij0123456789-",
        min_size=1,
        max_size=30,
    )
)
async def test_duplicate_asset_name_rejected(
    name: str,
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )

    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(
            title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}
        ),
    )

    # First asset creation must succeed
    await asset_service.create_asset(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=AssetCreate(name=name, type=AssetType.WORKSTATION),
    )

    # Second asset with the same name in the same case must be rejected
    with pytest.raises(HTTPException) as exc:
        await asset_service.create_asset(
            db_session,
            case_id=case.id,
            created_by=user.id,
            payload=AssetCreate(name=name, type=AssetType.SERVER),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_same_name_allowed_across_cases(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    """Uniqueness is scoped to a single case — not tenant-wide."""
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )

    case_a = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="A", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    case_b = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="B", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )

    payload = AssetCreate(name="shared-workstation-01", type=AssetType.WORKSTATION)
    a = await asset_service.create_asset(
        db_session, case_id=case_a.id, created_by=user.id, payload=payload
    )
    b = await asset_service.create_asset(
        db_session, case_id=case_b.id, created_by=user.id, payload=payload
    )
    assert a.name == b.name
    assert a.case_id != b.case_id

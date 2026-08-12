"""Property 15: Audit Log Completeness.

For any user action, an audit log entry SHALL be created containing:
user identity, action type, target resource, timestamp, and source IP
address. Service account entries SHALL be distinguishable from
interactive user entries.

Feature: watari-case-management, Property 15: Audit Log Completeness
**Validates: Requirements 13.1, 2.9**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.context import AuthContext, Role
from src.services import audit as audit_service

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


def _make_auth(user_id, tenant_id, *, is_service: bool = False) -> AuthContext:
    return AuthContext(
        user_id=user_id,
        tenant_id=tenant_id,
        username="u",
        display_name="U",
        role=Role.API_SERVICE_ACCOUNT if is_service else Role.ANALYST,
        session_id="s",
        is_service_account=is_service,
    )


@pytest.mark.asyncio
async def test_audit_entry_contains_all_required_fields(
    db_session: AsyncSession, tenant_factory, user_factory
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )
    auth = _make_auth(user.id, tenant.id)
    entry = await audit_service.record(
        db_session,
        auth=auth,
        action="POST /api/v1/cases",
        resource_type="case",
        resource_id=uuid4(),
        source_ip="192.0.2.1",
        user_agent="pytest",
    )
    assert entry.user_id == user.id
    assert entry.tenant_id == tenant.id
    assert entry.action
    assert entry.resource_type == "case"
    assert entry.created_at is not None
    assert entry.source_ip == "192.0.2.1"
    assert entry.is_service_account is False


@pytest.mark.asyncio
async def test_service_account_entries_are_flagged(
    db_session: AsyncSession, tenant_factory, user_factory
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )
    auth = _make_auth(user.id, tenant.id, is_service=True)
    entry = await audit_service.record(
        db_session,
        auth=auth,
        action="POST /api/v1/alerts",
        resource_type="alert",
    )
    assert entry.is_service_account is True

"""Property 3: Significant Events Produce Timeline Entries.

For any significant platform event (case creation, status change, task
change, observable addition, asset compromise, report generation), a
corresponding timeline entry SHALL be created with timestamp, acting
user, event type, and description.

Feature: watari-case-management, Property 3: Significant Events Produce Timeline Entries
**Validates: Requirements 3.4, 5.3, 8.2, 16.8, 18.7**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import TimelineEntry
from src.schemas.assets import AssetCreate, AssetType, AssetUpdate
from src.schemas.cases import CaseCreate, CaseSeverity, CaseStatus, CaseUpdate
from src.schemas.observables import ObservableCreate, ObservableType
from src.schemas.tasks import TaskCreate, TaskStatus, TaskUpdate
from src.services import assets as asset_service
from src.services import cases as case_service
from src.services import observables as observable_service
from src.services import tasks as task_service

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


async def _timeline_events(db: AsyncSession, case_id) -> list[TimelineEntry]:
    return list(
        (
            await db.execute(
                select(TimelineEntry).where(TimelineEntry.case_id == case_id)
            )
        ).scalars().all()
    )


@pytest.mark.asyncio
async def test_case_creation_produces_timeline_entry(
    db_session: AsyncSession, tenant_factory, user_factory
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
        payload=CaseCreate(title="C", severity=CaseSeverity.MEDIUM, tags=[], custom_fields={}),
    )
    events = await _timeline_events(db_session, case.id)
    assert any(e.event_type == "case_created" for e in events)
    for e in events:
        assert e.event_timestamp is not None
        assert e.description


@pytest.mark.asyncio
async def test_status_change_produces_timeline_entry(
    db_session: AsyncSession, tenant_factory, user_factory
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
        payload=CaseCreate(title="C", severity=CaseSeverity.MEDIUM, tags=[], custom_fields={}),
    )
    await case_service.update_case(
        db_session,
        case.id,
        CaseUpdate(status=CaseStatus.IN_PROGRESS),
        actor_id=user.id,
    )
    events = await _timeline_events(db_session, case.id)
    assert any(e.event_type == "status_changed" for e in events)


@pytest.mark.asyncio
async def test_task_status_change_produces_timeline_entry(
    db_session: AsyncSession, tenant_factory, user_factory
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
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    task = await task_service.create_task(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=TaskCreate(title="T1"),
    )
    await task_service.update_task(
        db_session, task.id, TaskUpdate(status=TaskStatus.DONE), actor_id=user.id
    )
    events = await _timeline_events(db_session, case.id)
    assert any(e.event_type == "task_status_changed" for e in events)


@pytest.mark.asyncio
async def test_observable_add_produces_timeline_entry(
    db_session: AsyncSession, tenant_factory, user_factory
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
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    await observable_service.create_observable(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=ObservableCreate(type=ObservableType.IP, value="1.2.3.4"),
    )
    events = await _timeline_events(db_session, case.id)
    assert any(e.event_type == "observable_added" for e in events)


@pytest.mark.asyncio
async def test_asset_compromise_change_produces_timeline_entry(
    db_session: AsyncSession, tenant_factory, user_factory
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
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    asset = await asset_service.create_asset(
        db_session,
        case_id=case.id,
        created_by=user.id,
        payload=AssetCreate(name="ws01", type=AssetType.WORKSTATION),
    )
    await asset_service.update_asset(
        db_session,
        asset.id,
        AssetUpdate(is_compromised=True),
        actor_id=user.id,
    )
    events = await _timeline_events(db_session, case.id)
    assert any(e.event_type == "asset_compromise_changed" for e in events)

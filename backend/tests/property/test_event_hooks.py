"""Property 24: Event Hook Triggering.

For any configured event hook mapping an event type to a processor
module, when that event occurs, the corresponding module SHALL be
triggered exactly once. Events without configured hooks SHALL NOT
trigger any module.

Feature: watari-case-management, Property 24: Event Hook Triggering
**Validates: Requirements 20.6**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Module, ModuleExecution
from src.modules.base import BaseModule, ModuleAPI, ModuleType, PlatformEvent, get_registry
from src.schemas.cases import CaseCreate, CaseSeverity
from src.services import cases as case_service
from src.services import modules as module_service

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


class _CountingModule(BaseModule):
    """Records each execute() call — one per hook trigger."""

    calls: list[dict[str, Any]] = []

    async def execute(
        self, context: ModuleAPI, config: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        _CountingModule.calls.append({"config": config, "payload": payload})
        return {"ok": True}


@pytest.mark.asyncio
async def test_event_fires_only_subscribed_modules(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    # Register two modules: one subscribed, one NOT subscribed
    get_registry().register("test.counting", _CountingModule)
    _CountingModule.calls = []

    subscribed = Module(
        name="subscribed",
        version="1.0",
        type="processor",
        entry_point="test.counting",
        is_enabled=True,
        subscribed_events=[PlatformEvent.OBSERVABLE_CREATED.value],
    )
    unsubscribed = Module(
        name="unsubscribed",
        version="1.0",
        type="processor",
        entry_point="test.counting",
        is_enabled=True,
        subscribed_events=[PlatformEvent.CASE_STATUS_CHANGED.value],
    )
    db_session.add_all([subscribed, unsubscribed])
    await db_session.flush()

    # Dispatch OBSERVABLE_CREATED — only `subscribed` should run.
    # The case must really exist: `dispatch_event` records a ModuleExecution
    # row whose case_id is a foreign key into `cases`.
    case = await case_service.create_case(
        db_session,
        tenant_id=tenant.id,
        created_by=user.id,
        payload=CaseCreate(title="C", severity=CaseSeverity.LOW, tags=[], custom_fields={}),
    )
    await module_service.dispatch_event(
        db_session,
        tenant_id=tenant.id,
        event=PlatformEvent.OBSERVABLE_CREATED,
        payload={"case_id": str(case.id), "observable_id": str(uuid4())},
        actor_id=user.id,
    )

    execs = list(
        (
            await db_session.execute(
                select(ModuleExecution).where(ModuleExecution.module_id.in_(
                    [subscribed.id, unsubscribed.id]
                ))
            )
        ).scalars().all()
    )
    assert len(execs) == 1
    assert execs[0].module_id == subscribed.id


@pytest.mark.asyncio
async def test_event_without_hooks_triggers_nothing(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)").bindparams(tid=str(tenant.id))
    )

    # No modules at all — dispatch should complete cleanly with empty result
    result = await module_service.dispatch_event(
        db_session,
        tenant_id=tenant.id,
        event=PlatformEvent.CASE_CREATED,
        payload={"case_id": str(uuid4())},
        actor_id=user.id,
    )
    assert result == []

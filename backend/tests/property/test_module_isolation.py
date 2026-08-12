"""Property 25: Module Failure Isolation.

For any module execution that fails (exception or timeout), the failure
SHALL be logged with error details, the platform SHALL continue operating
normally, and no other module or user operation SHALL be affected.

Feature: watari-case-management, Property 25: Module Failure Isolation
**Validates: Requirements 20.7**

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Module, ModuleExecution
from src.modules.base import BaseModule, ModuleAPI, get_registry
from src.services import modules as module_service

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


class _BoomModule(BaseModule):
    async def execute(
        self, context: ModuleAPI, config: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError("boom")


class _OKModule(BaseModule):
    async def execute(
        self, context: ModuleAPI, config: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        return {"ok": True}


@pytest.mark.asyncio
async def test_module_exception_recorded_as_failed(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )

    get_registry().register("test.boom", _BoomModule)
    module = Module(
        name="boom", version="1.0", type="processor",
        entry_point="test.boom", is_enabled=True,
    )
    db_session.add(module)
    await db_session.flush()

    exec_row = await module_service.execute_module(
        db_session,
        module_id=module.id,
        tenant_id=tenant.id,
        case_id=None,
        config={},
        payload={},
        actor_id=user.id,
    )
    assert exec_row.status == "failed"
    assert exec_row.error_message and "boom" in exec_row.error_message
    assert exec_row.completed_at is not None


@pytest.mark.asyncio
async def test_module_failure_does_not_affect_other_modules(
    db_session: AsyncSession,
    tenant_factory,
    user_factory,
) -> None:
    tenant = await tenant_factory()
    user = await user_factory(tenant.id)
    await db_session.execute(
        text("SET LOCAL app.current_tenant = :tid").bindparams(tid=str(tenant.id))
    )

    get_registry().register("test.boom", _BoomModule)
    get_registry().register("test.ok", _OKModule)
    boom_module = Module(
        name="boom-iso", version="1.0", type="processor",
        entry_point="test.boom", is_enabled=True,
    )
    ok_module = Module(
        name="ok-iso", version="1.0", type="processor",
        entry_point="test.ok", is_enabled=True,
    )
    db_session.add_all([boom_module, ok_module])
    await db_session.flush()

    boom_exec = await module_service.execute_module(
        db_session,
        module_id=boom_module.id,
        tenant_id=tenant.id,
        case_id=None,
        config={},
        payload={},
        actor_id=user.id,
    )
    ok_exec = await module_service.execute_module(
        db_session,
        module_id=ok_module.id,
        tenant_id=tenant.id,
        case_id=None,
        config={},
        payload={},
        actor_id=user.id,
    )

    assert boom_exec.status == "failed"
    assert ok_exec.status == "completed"
    assert ok_exec.result == {"ok": True}

"""Module service: install, configure, dispatch events, execute.

Module code itself is registered via `src.modules.base.get_registry()`
at application startup. This service handles:

- CRUD on the `modules` table
- Dispatching platform events to subscribed processor modules (async
  Celery jobs so the caller never blocks)
- Tracking executions in `module_executions` with status transitions
- Enforcing failure isolation (exceptions are caught and recorded)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Module, ModuleExecution
from src.modules.base import PlatformEvent, get_registry
from src.modules.runtime_api import SessionModuleAPI
from src.schemas.modules import ModuleRegister, ModuleUpdate

_log = logging.getLogger("watari.modules")


async def _get_module_or_404(db: AsyncSession, module_id: UUID) -> Module:
    m = (await db.execute(select(Module).where(Module.id == module_id))).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Module {module_id} not found")
    return m


# --- Module CRUD -------------------------------------------------------

async def list_modules(
    db: AsyncSession, *, limit: int = 100, offset: int = 0
) -> tuple[list[Module], int]:
    total = (await db.execute(select(func.count()).select_from(Module))).scalar_one()
    rows = (
        await db.execute(select(Module).order_by(Module.name.asc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)


async def register_module(db: AsyncSession, payload: ModuleRegister) -> Module:
    existing = (
        await db.execute(select(Module).where(Module.name == payload.name))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Module '{payload.name}' already registered")
    module = Module(
        name=payload.name,
        version=payload.version,
        type=payload.type.value,
        description=payload.description,
        config_schema=payload.config_schema,
        entry_point=payload.entry_point,
        supported_evidence_types=payload.supported_evidence_types,
        subscribed_events=payload.subscribed_events,
        is_enabled=True,
    )
    db.add(module)
    await db.flush()
    await db.refresh(module)
    return module


async def update_module(
    db: AsyncSession, module_id: UUID, payload: ModuleUpdate
) -> Module:
    module = await _get_module_or_404(db, module_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(module, key, value)
    await db.flush()
    await db.refresh(module)
    return module


async def delete_module(db: AsyncSession, module_id: UUID) -> None:
    module = await _get_module_or_404(db, module_id)
    await db.delete(module)
    await db.flush()


async def list_executions(
    db: AsyncSession,
    *,
    module_id: UUID | None = None,
    tenant_id: UUID | None = None,
    case_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ModuleExecution], int]:
    base = select(ModuleExecution)
    if module_id:
        base = base.where(ModuleExecution.module_id == module_id)
    if tenant_id:
        base = base.where(ModuleExecution.tenant_id == tenant_id)
    if case_id:
        base = base.where(ModuleExecution.case_id == case_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(ModuleExecution.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


# --- Execution ---------------------------------------------------------

async def execute_module(
    db: AsyncSession,
    *,
    module_id: UUID,
    tenant_id: UUID,
    case_id: UUID | None,
    config: dict[str, Any],
    payload: dict[str, Any],
    actor_id: UUID | None,
    trigger_event: str | None = None,
) -> ModuleExecution:
    """Execute a module synchronously within the current transaction.

    Typically called by a Celery worker, not directly from an API route.
    Records a ModuleExecution row regardless of outcome; failures are
    caught and logged rather than propagated.
    """
    module = await _get_module_or_404(db, module_id)

    execution = ModuleExecution(
        module_id=module.id,
        tenant_id=tenant_id,
        case_id=case_id,
        status="running",
        trigger_event=trigger_event,
        config=config,
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    await db.flush()

    registry = get_registry()
    module_cls = registry.get(module.entry_point)
    if module_cls is None:
        execution.status = "failed"
        execution.error_message = (
            f"Module entry_point '{module.entry_point}' is not registered"
        )
        execution.completed_at = datetime.now(UTC)
        await db.flush()
        await db.refresh(execution)
        return execution

    try:
        instance = module_cls()
        api = SessionModuleAPI(db, actor_id=actor_id)
        result = await instance.execute(api, config, payload)
        execution.status = "completed"
        execution.result = result
    except Exception as exc:  # noqa: BLE001
        _log.exception(
            "module execution failed: module_id=%s entry_point=%s",
            module.id,
            module.entry_point,
        )
        execution.status = "failed"
        execution.error_message = str(exc)
    finally:
        execution.completed_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(execution)
    return execution


async def dispatch_event(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    event: PlatformEvent,
    payload: dict[str, Any],
    actor_id: UUID | None,
) -> list[UUID]:
    """Queue execution for every enabled module subscribed to the event.

    Returns the IDs of the module_executions rows that were created
    (one per dispatched module).
    """
    # Find matching modules
    rows = (
        await db.execute(
            select(Module)
            .where(Module.is_enabled.is_(True))
            .where(Module.type == "processor")
        )
    ).scalars().all()
    matched = [m for m in rows if event.value in (m.subscribed_events or [])]

    queued: list[UUID] = []
    for module in matched:
        # Enqueue via Celery when possible; else execute synchronously
        try:
            from src.worker.tasks import execute_processor_module  # lazy

            task = execute_processor_module.delay(
                str(module.id),
                str(tenant_id),
                payload.get("case_id"),
                event.value,
                payload,
                str(actor_id) if actor_id else None,
            )
            # Best-effort: record a placeholder execution row for UI visibility
            execution = ModuleExecution(
                module_id=module.id,
                tenant_id=tenant_id,
                case_id=UUID(payload["case_id"]) if payload.get("case_id") else None,
                status="queued",
                trigger_event=event.value,
                config={},
                result={"celery_task_id": task.id},
            )
            db.add(execution)
            await db.flush()
            queued.append(execution.id)
        except Exception:
            # Synchronous fallback for environments without a worker
            exec_row = await execute_module(
                db,
                module_id=module.id,
                tenant_id=tenant_id,
                case_id=UUID(payload["case_id"]) if payload.get("case_id") else None,
                config={},
                payload=payload,
                actor_id=actor_id,
                trigger_event=event.value,
            )
            queued.append(exec_row.id)
    return queued


__all__ = [
    "list_modules",
    "register_module",
    "update_module",
    "delete_module",
    "list_executions",
    "execute_module",
    "dispatch_event",
]

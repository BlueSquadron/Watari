"""Platform event dispatcher.

Thin wrapper around `modules.dispatch_event` that services call when a
significant event happens. Failures are swallowed so module issues do
not break user-facing requests (Property 25: module failure isolation).
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.base import PlatformEvent


async def fire(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    event: PlatformEvent,
    payload: dict[str, Any],
    actor_id: UUID | None,
) -> None:
    """Dispatch an event to subscribed modules (best-effort).

    Any exception inside the module system is logged but does NOT
    propagate — the caller's request must continue to succeed.
    """
    with suppress(Exception):
        from . import modules as module_service  # lazy to avoid circular import

        await module_service.dispatch_event(
            db,
            tenant_id=tenant_id,
            event=event,
            payload=payload,
            actor_id=actor_id,
        )


__all__ = ["fire"]

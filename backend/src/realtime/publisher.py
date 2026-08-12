"""Small helper used by service layers to publish realtime events.

Services call ``publish()`` after a successful mutation. We swallow
exceptions so realtime failures never break the request — pub/sub is a
best-effort channel.
"""

from __future__ import annotations

from contextlib import suppress
from typing import Any
from uuid import UUID

from .hub import get_hub


async def publish_case(
    *,
    case_id: UUID,
    tenant_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    actor_id: UUID | None = None,
    actor_display_name: str | None = None,
) -> None:
    with suppress(Exception):
        await get_hub().publish_case_event(
            case_id=case_id,
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload or {},
            actor_id=actor_id,
            actor_display_name=actor_display_name,
        )


async def publish_tenant(
    *,
    tenant_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    actor_id: UUID | None = None,
    actor_display_name: str | None = None,
) -> None:
    with suppress(Exception):
        await get_hub().publish_tenant_event(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload or {},
            actor_id=actor_id,
            actor_display_name=actor_display_name,
        )


__all__ = ["publish_case", "publish_tenant"]

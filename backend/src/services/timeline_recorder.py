"""Internal helper for recording automatic timeline entries.

Used by other services (cases, tasks, observables, assets, evidence, etc.)
to record significant events without each service having to duplicate the
boilerplate. Each recorded entry is also published to the realtime hub so
subscribed WebSocket clients see live updates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import TimelineEntry
from src.realtime.publisher import publish_case


async def record_event(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    case_id: UUID,
    event_type: str,
    description: str,
    category: str | None = None,
    actor_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    event_timestamp: datetime | None = None,
) -> TimelineEntry:
    """Create a timeline entry marked as automatic (is_automatic=True)."""
    entry = TimelineEntry(
        tenant_id=tenant_id,
        case_id=case_id,
        event_type=event_type,
        event_timestamp=event_timestamp or datetime.now(UTC),
        description=description,
        category=category,
        actor_id=actor_id,
        is_automatic=True,
        event_metadata=metadata or {},
    )
    db.add(entry)
    await db.flush()

    # Realtime fan-out (best-effort; never raises)
    await publish_case(
        case_id=case_id,
        tenant_id=tenant_id,
        event_type=event_type,
        payload={
            "timeline_entry_id": str(entry.id),
            "description": description,
            "category": category,
            "metadata": metadata or {},
        },
        actor_id=actor_id,
    )
    return entry


__all__ = ["record_event"]

"""WebSocket hub with Redis pub/sub fan-out.

Architecture:

1. Clients connect to `/api/v1/realtime/cases/{case_id}` or
   `/api/v1/realtime/tenants/{tenant_id}` with a JWT in the `token`
   query param (browsers can't set custom headers on WebSocket upgrade).
2. Each instance of the API registers its connections in an in-process
   map (tenant_id/case_id -> list[WebSocket]).
3. When a mutation happens, services call `publish_case_event()` or
   `publish_tenant_event()`, which writes the event to a Redis pub/sub
   channel (one channel per case, one per tenant).
4. Every API instance subscribes to its own channels on startup and
   forwards received messages to its connected WebSockets.

The Redis hop means the hub works across horizontally-scaled API
instances: publishing on instance A delivers to a client on instance B.

Presence tracking (who's viewing a case) is a TTL-backed set in Redis:
`presence:case:{case_id}` with member = user_id and 30s TTL per entry,
refreshed by the client via a ping message.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket
from redis.asyncio import Redis

_log = logging.getLogger("watari.realtime")

_CASE_CHANNEL = "case:{case_id}"
_TENANT_CHANNEL = "tenant:{tenant_id}"
_PRESENCE_KEY = "presence:case:{case_id}"
_PRESENCE_TTL_SECONDS = 30


@dataclass(frozen=True, slots=True)
class RealtimeEvent:
    """Message delivered to WebSocket clients."""

    type: str  # e.g. "case_updated", "observable_added"
    case_id: str | None
    tenant_id: str
    payload: dict[str, Any]
    actor_id: str | None
    actor_display_name: str | None
    timestamp: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "case_id": self.case_id,
                "tenant_id": self.tenant_id,
                "payload": self.payload,
                "actor": (
                    {"user_id": self.actor_id, "display_name": self.actor_display_name}
                    if self.actor_id
                    else None
                ),
                "timestamp": self.timestamp,
            }
        )


class WebSocketHub:
    """In-process connection manager + Redis pub/sub bridge."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._case_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._tenant_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._pubsub_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._stopped = False

    # -------- Connection management ---------

    async def connect_case(self, websocket: WebSocket, case_id: str, user_id: str) -> None:
        async with self._lock:
            self._case_connections[case_id].add(websocket)
        await self._touch_presence(case_id, user_id)

    async def disconnect_case(self, websocket: WebSocket, case_id: str, user_id: str) -> None:
        async with self._lock:
            self._case_connections[case_id].discard(websocket)
            if not self._case_connections[case_id]:
                self._case_connections.pop(case_id, None)
        await self._remove_presence(case_id, user_id)

    async def connect_tenant(self, websocket: WebSocket, tenant_id: str) -> None:
        async with self._lock:
            self._tenant_connections[tenant_id].add(websocket)

    async def disconnect_tenant(self, websocket: WebSocket, tenant_id: str) -> None:
        async with self._lock:
            self._tenant_connections[tenant_id].discard(websocket)
            if not self._tenant_connections[tenant_id]:
                self._tenant_connections.pop(tenant_id, None)

    # -------- Publish ---------

    async def publish_case_event(
        self,
        *,
        case_id: UUID,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        actor_id: UUID | None = None,
        actor_display_name: str | None = None,
    ) -> None:
        event = RealtimeEvent(
            type=event_type,
            case_id=str(case_id),
            tenant_id=str(tenant_id),
            payload=payload,
            actor_id=str(actor_id) if actor_id else None,
            actor_display_name=actor_display_name,
            timestamp=datetime.now(UTC).isoformat(),
        )
        # Fan out to case subscribers AND tenant activity feed
        await self._redis.publish(_CASE_CHANNEL.format(case_id=case_id), event.to_json())
        await self._redis.publish(_TENANT_CHANNEL.format(tenant_id=tenant_id), event.to_json())

    async def publish_tenant_event(
        self,
        *,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        actor_id: UUID | None = None,
        actor_display_name: str | None = None,
    ) -> None:
        event = RealtimeEvent(
            type=event_type,
            case_id=None,
            tenant_id=str(tenant_id),
            payload=payload,
            actor_id=str(actor_id) if actor_id else None,
            actor_display_name=actor_display_name,
            timestamp=datetime.now(UTC).isoformat(),
        )
        await self._redis.publish(_TENANT_CHANNEL.format(tenant_id=tenant_id), event.to_json())

    # -------- Presence ---------

    async def _touch_presence(self, case_id: str, user_id: str) -> None:
        key = _PRESENCE_KEY.format(case_id=case_id)
        await self._redis.zadd(key, {user_id: datetime.now(UTC).timestamp()})
        await self._redis.expire(key, _PRESENCE_TTL_SECONDS * 4)

    async def _remove_presence(self, case_id: str, user_id: str) -> None:
        key = _PRESENCE_KEY.format(case_id=case_id)
        await self._redis.zrem(key, user_id)

    async def get_active_viewers(self, case_id: str) -> list[str]:
        """Return user_ids currently viewing the case (within presence TTL)."""
        key = _PRESENCE_KEY.format(case_id=case_id)
        cutoff = datetime.now(UTC).timestamp() - _PRESENCE_TTL_SECONDS
        # Remove stale entries
        await self._redis.zremrangebyscore(key, 0, cutoff)
        members = await self._redis.zrange(key, 0, -1)
        return [m for m in members] if members else []

    # -------- Pub/sub loop ---------

    async def start_listener(self) -> None:
        """Start the Redis pub/sub listener task.

        Uses a psubscribe pattern so we receive events for all case and
        tenant channels in one connection. Spawned on application startup.
        """
        if self._pubsub_task is not None:
            return
        self._stopped = False
        self._pubsub_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        self._stopped = True
        if self._pubsub_task is not None:
            self._pubsub_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._pubsub_task
            self._pubsub_task = None

    async def _listen(self) -> None:
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        await pubsub.psubscribe("case:*", "tenant:*")
        try:
            async for message in pubsub.listen():
                if self._stopped:
                    break
                if message is None or message.get("type") != "pmessage":
                    continue
                channel = message["channel"]
                data = message["data"]
                await self._deliver(channel, data)
        except Exception:  # noqa: BLE001
            _log.exception("pubsub listener error")
        finally:
            await pubsub.aclose()

    async def _deliver(self, channel: str, data: str) -> None:
        connections: set[WebSocket] = set()
        if channel.startswith("case:"):
            case_id = channel.split(":", 1)[1]
            async with self._lock:
                connections = set(self._case_connections.get(case_id, ()))
        elif channel.startswith("tenant:"):
            tenant_id = channel.split(":", 1)[1]
            async with self._lock:
                connections = set(self._tenant_connections.get(tenant_id, ()))

        for ws in connections:
            with suppress(Exception):
                await ws.send_text(data)


_hub: WebSocketHub | None = None


def get_hub() -> WebSocketHub:
    global _hub
    if _hub is None:
        from src.utils import get_redis

        _hub = WebSocketHub(get_redis())
    return _hub


__all__ = ["RealtimeEvent", "WebSocketHub", "get_hub"]

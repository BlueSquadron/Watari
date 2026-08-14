"""Session management with Redis-backed TTL for inactivity timeout.

Each interactive login produces a `session_id` (UUID) that is stored
in the JWT `session_id` claim and mirrored in Redis under
``session:{user_id}:{session_id}``. The Redis TTL is set to the user's
configured `inactivity_timeout_minutes`.

Each authenticated request "touches" the session, extending the TTL.
If the key has expired by the time a request arrives, the session is
considered invalid and the user must re-authenticate.

API-key service accounts do not use sessions — their validity is
controlled entirely by the user row's `is_active` flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from redis.asyncio import Redis

_SESSION_KEY_TEMPLATE = "session:{user_id}:{session_id}"


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Metadata stored alongside an active session."""

    user_id: UUID
    session_id: str
    created_at: datetime
    source_ip: str | None = None
    user_agent: str | None = None


def _key(user_id: UUID, session_id: str) -> str:
    return _SESSION_KEY_TEMPLATE.format(user_id=user_id, session_id=session_id)


async def create_session(
    redis: Redis,
    user_id: UUID,
    inactivity_timeout_minutes: int,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> SessionRecord:
    """Create a new session record in Redis and return it."""
    session_id = str(uuid4())
    record = SessionRecord(
        user_id=user_id,
        session_id=session_id,
        created_at=datetime.now(UTC),
        source_ip=source_ip,
        user_agent=user_agent,
    )
    ttl_seconds = inactivity_timeout_minutes * 60
    await redis.set(
        _key(user_id, session_id),
        _serialize(record),
        ex=ttl_seconds,
    )
    return record


async def is_session_active(redis: Redis, user_id: UUID, session_id: str) -> bool:
    """Return True if the session key still exists in Redis."""
    return await redis.exists(_key(user_id, session_id)) > 0


async def touch_session(
    redis: Redis,
    user_id: UUID,
    session_id: str,
    inactivity_timeout_minutes: int,
) -> bool:
    """Reset the session TTL; return True if the session was still active."""
    ttl_seconds = inactivity_timeout_minutes * 60
    result = await redis.expire(_key(user_id, session_id), ttl_seconds)
    return bool(result)


async def invalidate_session(redis: Redis, user_id: UUID, session_id: str) -> None:
    """Delete a session key immediately (explicit logout)."""
    await redis.delete(_key(user_id, session_id))


async def invalidate_all_sessions(redis: Redis, user_id: UUID) -> int:
    """Delete all active sessions for a user; return count of deleted sessions."""
    deleted = 0
    pattern = _SESSION_KEY_TEMPLATE.format(user_id=user_id, session_id="*")
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)
        deleted += 1
    return deleted


def _serialize(record: SessionRecord) -> str:
    # Lightweight serialization — we don't use JSON because the record
    # is opaque beyond the key existence check.
    return (
        f"{record.user_id}|{record.session_id}|{record.created_at.isoformat()}|"
        f"{record.source_ip or ''}|{record.user_agent or ''}"
    )


__all__ = [
    "SessionRecord",
    "create_session",
    "is_session_active",
    "touch_session",
    "invalidate_session",
    "invalidate_all_sessions",
]

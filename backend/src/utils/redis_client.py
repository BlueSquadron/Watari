"""Shared async Redis client."""

from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis, from_url

from .config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Return a cached async Redis client configured from settings."""
    settings = get_settings()
    return from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


__all__ = ["get_redis"]

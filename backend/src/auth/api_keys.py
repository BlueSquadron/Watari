"""API key generation, hashing, and authentication for service accounts.

Service accounts are users with `is_service_account=True` and
`role=API_SERVICE_ACCOUNT`. They authenticate exclusively via the
`X-API-Key` header — JWT and the web UI are not accessible to them.

API keys are generated with a `wat_` prefix so they are easy to spot in
logs and secret scanners, followed by 43 characters of URL-safe base64
entropy (256 bits). The plaintext key is shown exactly once at creation
and only the SHA-256 hash is stored.

The effective permissions of a service account are inherited from the
`role` or `permissions` field stored on the user row; this module only
handles identity resolution.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db, get_db_unscoped
from src.models import User

from .context import AuthContext, Role
from .dependencies import _scope_session

_API_KEY_PREFIX = "wat_"
_API_KEY_ENTROPY_BYTES = 32  # -> 43 base64 chars
_API_KEY_HEADER = "X-API-Key"

_api_key_scheme = APIKeyHeader(name=_API_KEY_HEADER, auto_error=False)


def generate_api_key() -> str:
    """Generate a new plaintext API key.

    Returns a string like ``wat_<43 base64-url-safe chars>``. Callers MUST
    persist only the hash returned by :func:`hash_api_key` and surface the
    plaintext to the user exactly once.
    """
    token = secrets.token_urlsafe(_API_KEY_ENTROPY_BYTES)
    return f"{_API_KEY_PREFIX}{token}"


def hash_api_key(api_key: str) -> str:
    """Return the SHA-256 hex digest of a plaintext API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(plain: str, hashed: str) -> bool:
    """Constant-time comparison of an API key against its stored hash."""
    return secrets.compare_digest(hash_api_key(plain), hashed)


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key",
    headers={"WWW-Authenticate": "ApiKey"},
)


async def _load_service_account(key: str, db: AsyncSession) -> AuthContext:
    """Resolve a plaintext API key to an AuthContext or raise 401."""
    if not key or not key.startswith(_API_KEY_PREFIX):
        raise _UNAUTHORIZED

    key_hash = hash_api_key(key)
    user = (
        await db.execute(
            select(User).where(
                User.api_key_hash == key_hash,
                User.is_service_account.is_(True),
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise _UNAUTHORIZED

    # Constant-time re-check to guard against rare SHA-256 collisions
    # and side-channels — the DB lookup above already used the hash so
    # this is essentially belt-and-braces.
    assert user.api_key_hash is not None
    if not secrets.compare_digest(key_hash, user.api_key_hash):
        raise _UNAUTHORIZED

    return AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
        role=Role(user.role),
        session_id=f"apikey:{user.id}",
        is_service_account=True,
    )


async def get_service_account(
    request: Request,
    api_key: Annotated[str | None, Security(_api_key_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    scoped_db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    """FastAPI dependency for service-account-only endpoints.

    Scopes the request session to the service account's tenant so RLS is in
    force before the endpoint runs — see `get_current_user` for why this
    happens here rather than in `get_db`.
    """
    if api_key is None:
        raise _UNAUTHORIZED
    auth_context = await _load_service_account(api_key, db)
    request.state.auth_context = auth_context
    await _scope_session(scoped_db, auth_context)
    return auth_context


async def get_service_account_optional(
    request: Request,
    api_key: Annotated[str | None, Security(_api_key_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    scoped_db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext | None:
    """Like `get_service_account` but returns None when no API key is present."""
    if api_key is None:
        return None
    try:
        auth_context = await _load_service_account(api_key, db)
    except HTTPException:
        return None
    request.state.auth_context = auth_context
    await _scope_session(scoped_db, auth_context)
    return auth_context


ServiceAccountDep = Annotated[AuthContext, Depends(get_service_account)]
OptionalServiceAccountDep = Annotated[AuthContext | None, Depends(get_service_account_optional)]


__all__ = [
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "ServiceAccountDep",
    "OptionalServiceAccountDep",
    "get_service_account",
    "get_service_account_optional",
]

"""FastAPI dependencies for authentication and authorization.

The JWT flow lives here. API-key-based service account auth is added by
the `api_keys` module (task 3.3). The `get_current_user` dependency
resolves the active `AuthContext`, stashes it on `request.state` so the
RLS-aware `get_db` dependency can pick up the tenant, verifies the
session is still active in Redis (and touches its TTL for inactivity
timeout enforcement), and raises 401 for missing or invalid credentials.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import TenantContext, apply_tenant_context, get_db, get_db_unscoped
from src.models import User
from src.utils import get_redis

from .context import AuthContext, Role
from .jwt import TokenPayload, decode_token
from .sessions import is_session_active, touch_session

OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_SESSION_EXPIRED_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Session expired due to inactivity",
    headers={"WWW-Authenticate": "Bearer"},
)


async def _load_user_from_token(token: str, db: AsyncSession) -> AuthContext:
    """Decode the token, verify the user, check the session, and build an AuthContext."""
    try:
        payload: TokenPayload = decode_token(token)
    except JWTError:
        raise _CREDENTIALS_EXCEPTION from None

    if payload.token_type != "access":
        raise _CREDENTIALS_EXCEPTION

    user = (await db.execute(select(User).where(User.id == payload.sub))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION

    # Verify the session is still active (inactivity timeout enforcement).
    # Service accounts do not use sessions.
    redis = get_redis()
    if not await is_session_active(redis, user.id, payload.session_id):
        raise _SESSION_EXPIRED_EXCEPTION

    # Touch the session TTL to extend it based on continued activity.
    await touch_session(redis, user.id, payload.session_id, user.inactivity_timeout_minutes)

    return AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
        role=Role(user.role),
        session_id=payload.session_id,
        is_service_account=user.is_service_account,
    )


async def _scope_session(session: AsyncSession, auth: AuthContext) -> None:
    """Apply `auth`'s tenant to the request-scoped session, for RLS."""
    await apply_tenant_context(
        session,
        TenantContext(tenant_id=auth.tenant_id, is_platform_admin=auth.is_platform_admin),
    )


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    scoped_db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    """Resolve the current authenticated user from the Authorization header.

    The lookup itself runs on an unscoped session: there is no tenant to scope
    to until the user is known.

    Having resolved them, this scopes the *request's* session — the same
    object the endpoint receives, since FastAPI caches `get_db` per request —
    so that RLS is in force before any handler runs. Doing it here rather than
    in `get_db` is deliberate: routers declare `db` before `auth`, so `get_db`
    resolves first and cannot see the identity. Pushing the context down from
    the auth dependency makes the ordering a property of the dependency graph
    instead of parameter order in every signature.
    """
    if token is None:
        raise _CREDENTIALS_EXCEPTION
    auth_context = await _load_user_from_token(token, db)
    request.state.auth_context = auth_context
    await _scope_session(scoped_db, auth_context)
    return auth_context


async def get_current_user_optional(
    request: Request,
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
    scoped_db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext | None:
    """Like `get_current_user` but returns None when no credentials are present."""
    if token is None:
        return None
    try:
        auth_context = await _load_user_from_token(token, db)
    except HTTPException:
        return None
    request.state.auth_context = auth_context
    await _scope_session(scoped_db, auth_context)
    return auth_context


CurrentUserDep = Annotated[AuthContext, Depends(get_current_user)]
OptionalCurrentUserDep = Annotated[AuthContext | None, Depends(get_current_user_optional)]


__all__ = [
    "OAUTH2_SCHEME",
    "CurrentUserDep",
    "OptionalCurrentUserDep",
    "get_current_user",
    "get_current_user_optional",
]

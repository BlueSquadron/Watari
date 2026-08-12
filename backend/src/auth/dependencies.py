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

from src.db import get_db_unscoped
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

    user = (
        await db.execute(select(User).where(User.id == payload.sub))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXCEPTION

    # Verify the session is still active (inactivity timeout enforcement).
    # Service accounts do not use sessions.
    redis = get_redis()
    if not await is_session_active(redis, user.id, payload.session_id):
        raise _SESSION_EXPIRED_EXCEPTION

    # Touch the session TTL to extend it based on continued activity.
    await touch_session(
        redis, user.id, payload.session_id, user.inactivity_timeout_minutes
    )

    return AuthContext(
        user_id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        display_name=user.display_name,
        role=Role(user.role),
        session_id=payload.session_id,
        is_service_account=user.is_service_account,
    )


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
) -> AuthContext:
    """Resolve the current authenticated user from the Authorization header.

    Uses an unscoped DB session for the user lookup because RLS is not yet
    engaged at this point — the tenant context is being constructed here.
    Once resolved, the auth context is stashed on `request.state` so that
    downstream dependencies (notably `get_tenant_context`) can pick it up.
    """
    if token is None:
        raise _CREDENTIALS_EXCEPTION
    auth_context = await _load_user_from_token(token, db)
    request.state.auth_context = auth_context
    return auth_context


async def get_current_user_optional(
    request: Request,
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
) -> AuthContext | None:
    """Like `get_current_user` but returns None when no credentials are present."""
    if token is None:
        return None
    try:
        auth_context = await _load_user_from_token(token, db)
    except HTTPException:
        return None
    request.state.auth_context = auth_context
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

"""Unified authentication dependency accepting either JWT or API key.

Most application routes should accept both interactive users (JWT) and
service accounts (API key). Rather than duplicating dependencies, this
module provides `get_principal` which tries each scheme in order:

1. ``Authorization: Bearer <jwt>`` — interactive user
2. ``X-API-Key: <key>`` — service account

The first one to succeed wins. If neither is present or valid, the
request is rejected with 401.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db_unscoped

from .api_keys import _load_service_account  # internal reuse
from .context import AuthContext
from .dependencies import OAUTH2_SCHEME, _load_user_from_token

_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_principal(
    request: Request,
    token: Annotated[str | None, Depends(OAUTH2_SCHEME)],
    api_key: Annotated[str | None, Security(_api_key_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
) -> AuthContext:
    """Return the AuthContext for either a JWT-authenticated user or a service account."""
    if token is not None:
        auth = await _load_user_from_token(token, db)
        request.state.auth_context = auth
        return auth
    if api_key is not None:
        auth = await _load_service_account(api_key, db)
        request.state.auth_context = auth
        return auth
    raise _UNAUTHORIZED


PrincipalDep = Annotated[AuthContext, Depends(get_principal)]


__all__ = ["PrincipalDep", "get_principal"]

"""JWT token creation, validation, and payload typing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from pydantic import BaseModel

from src.utils import get_settings

_ACCESS_TOKEN_TYPE = "access"
_REFRESH_TOKEN_TYPE = "refresh"
_REFRESH_TOKEN_DAYS = 7


class TokenPayload(BaseModel):
    """Typed representation of a decoded JWT payload."""

    sub: UUID
    tenant_id: UUID
    role: str
    session_id: str
    token_type: str
    iat: int
    exp: int
    jti: str


def _build_payload(
    subject: dict[str, Any],
    token_type: str,
    expires_delta: timedelta,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        **{k: str(v) if isinstance(v, UUID) else v for k, v in subject.items()},
        "token_type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid4()),
    }


def create_access_token(
    subject: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    The subject must contain at minimum `sub` (user id), `tenant_id`,
    `role`, and `session_id`. Extra fields are preserved in the token.
    """
    settings = get_settings()
    delta = expires_delta or timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = _build_payload(subject, _ACCESS_TOKEN_TYPE, delta)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: dict[str, Any]) -> str:
    """Create a long-lived refresh token (default 7 days)."""
    settings = get_settings()
    payload = _build_payload(
        subject, _REFRESH_TOKEN_TYPE, timedelta(days=_REFRESH_TOKEN_DAYS)
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT; raise JWTError if invalid or expired."""
    settings = get_settings()
    try:
        raw = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise
    return TokenPayload.model_validate(raw)


__all__ = [
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]

"""Authentication endpoints: login, logout, token refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    CurrentUserDep,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from src.auth.sessions import (
    create_session,
    invalidate_session,
)
from src.db import get_db_unscoped
from src.models import User
from src.schemas.common import ApiResponse
from src.schemas.users import (
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserResponse,
)
from src.utils import get_redis, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
) -> ApiResponse[LoginResponse]:
    """Authenticate with username and password; return a JWT access token."""
    settings = get_settings()

    # Find user by username. We do not reveal whether the username exists.
    user = (
        await db.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or user.password_hash is None
        or user.is_service_account
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Record the login time (best-effort). Refresh afterwards so we see
    # the server-side updated_at value when serialising below.
    from datetime import UTC, datetime

    user.last_login_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(user)

    # Create a Redis-backed session
    redis = get_redis()
    source_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    session = await create_session(
        redis,
        user_id=user.id,
        inactivity_timeout_minutes=user.inactivity_timeout_minutes,
        source_ip=source_ip,
        user_agent=user_agent,
    )

    subject = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
        "session_id": session.session_id,
    }
    access_token = create_access_token(subject)
    refresh_token = create_refresh_token(subject)

    return ApiResponse(
        data=LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
    )


@router.post("/refresh", response_model=ApiResponse[TokenRefreshResponse])
async def refresh_token(
    payload: TokenRefreshRequest,
) -> ApiResponse[TokenRefreshResponse]:
    """Exchange a valid refresh token for a new access token."""
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    if decoded.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not a refresh token",
        )
    settings = get_settings()
    subject = {
        "sub": str(decoded.sub),
        "tenant_id": str(decoded.tenant_id),
        "role": decoded.role,
        "session_id": decoded.session_id,
    }
    new_access = create_access_token(subject)
    return ApiResponse(
        data=TokenRefreshResponse(
            access_token=new_access,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(auth: CurrentUserDep) -> None:
    """Invalidate the caller's session."""
    redis = get_redis()
    await invalidate_session(redis, auth.user_id, auth.session_id)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(
    auth: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_db_unscoped)],
) -> ApiResponse[UserResponse]:
    """Return the profile of the currently authenticated user."""
    user = (await db.execute(select(User).where(User.id == auth.user_id))).scalar_one()
    return ApiResponse(data=UserResponse.model_validate(user))


__all__ = ["router"]

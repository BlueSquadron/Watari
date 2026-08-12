"""User schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.auth.context import Role


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    role: Role
    password: str | None = Field(
        default=None, min_length=8, description="Required unless external IdP creates the user"
    )
    inactivity_timeout_minutes: int = Field(default=30, ge=5, le=10080)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: Role | None = None
    is_active: bool | None = None
    inactivity_timeout_minutes: int | None = Field(default=None, ge=5, le=10080)
    permissions: list[dict[str, Any]] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    username: str
    email: str
    display_name: str
    role: Role
    is_active: bool
    is_service_account: bool
    permissions: list[dict[str, Any]]
    last_login_at: datetime | None
    inactivity_timeout_minutes: int
    created_at: datetime
    updated_at: datetime


class ServiceAccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=1, max_length=255)
    role: Role = Field(description="Must be analyst or read_only")
    permissions: list[dict[str, Any]] = Field(default_factory=list)


class ServiceAccountCreated(BaseModel):
    """Service account creation response — includes the plaintext API key ONCE."""

    model_config = ConfigDict(from_attributes=True)

    user: UserResponse
    api_key: str = Field(
        description="Plaintext API key. Shown once. Store it securely — it cannot be recovered."
    )


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    expires_in: int


__all__ = [
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "PasswordChange",
    "ServiceAccountCreate",
    "ServiceAccountCreated",
    "LoginRequest",
    "LoginResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
]

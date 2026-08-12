"""Authentication context and role definitions."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """User roles recognized by the platform."""

    PLATFORM_ADMIN = "platform_admin"
    TENANT_ADMIN = "tenant_admin"
    ANALYST = "analyst"
    READ_ONLY = "read_only"
    API_SERVICE_ACCOUNT = "api_service_account"


class AuthContext(BaseModel):
    """The authenticated principal for a request.

    Populated either by the JWT dependency (interactive users) or by the
    API key dependency (service accounts). Immutable once created so it
    can be passed around freely.
    """

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    tenant_id: UUID
    username: str
    display_name: str
    role: Role
    session_id: str
    is_service_account: bool = False

    @property
    def is_platform_admin(self) -> bool:
        """Whether this principal has platform-wide administrative privileges."""
        return self.role == Role.PLATFORM_ADMIN

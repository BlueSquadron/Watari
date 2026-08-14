"""User model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TS, Base, BaseModel


class User(BaseModel, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        CheckConstraint(
            "role IN ('platform_admin', 'tenant_admin', 'analyst', "
            "'read_only', 'api_service_account')",
            name="ck_users_role",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_service_account: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    last_login_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    inactivity_timeout_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="30"
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")  # noqa: F821

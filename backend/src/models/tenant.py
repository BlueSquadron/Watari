"""Tenant model."""

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Tenant(BaseModel, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    custom_fields_schema: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")  # noqa: F821
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="tenant")  # noqa: F821

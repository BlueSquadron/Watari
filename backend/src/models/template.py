"""CaseTemplate model."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class CaseTemplate(BaseModel, Base):
    __tablename__ = "case_templates"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    tasks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User")  # noqa: F821

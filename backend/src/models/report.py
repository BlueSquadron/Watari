"""ReportTemplate and Report models."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base, BaseModel


class ReportTemplate(BaseModel, Base):
    __tablename__ = "report_templates"
    __table_args__ = (
        CheckConstraint(
            "type IN ('investigation', 'activity')",
            name="ck_report_templates_type",
        ),
        CheckConstraint(
            "format IN ('docx', 'markdown', 'html')",
            name="ck_report_templates_format",
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    tag_schema: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    creator: Mapped["User"] = relationship("User")  # noqa: F821


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_templates.id"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    generated_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

    # Relationships
    case: Mapped["Case"] = relationship("Case")  # noqa: F821
    template: Mapped["ReportTemplate"] = relationship("ReportTemplate")
    generator: Mapped["User"] = relationship("User")  # noqa: F821

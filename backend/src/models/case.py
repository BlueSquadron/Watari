"""Case model."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TS, Base, BaseModel


class Case(BaseModel, Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "case_number", name="uq_cases_tenant_case_number"),
        CheckConstraint(
            "status IN ('new', 'in_progress', 'pending', 'resolved', 'closed')",
            name="ck_cases_status",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'informational')",
            name="ck_cases_severity",
        ),
        CheckConstraint(
            "outcome IN ('true_positive', 'false_positive', 'indeterminate', 'not_applicable')",
            name="ck_cases_outcome",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="new")
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_templates.id"), nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    merged_from: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="cases")  # noqa: F821
    assignee: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[assignee_id]
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    template: Mapped["CaseTemplate | None"] = relationship("CaseTemplate")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="case")  # noqa: F821
    observables: Mapped[list["Observable"]] = relationship(  # noqa: F821
        "Observable", back_populates="case"
    )
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="case")  # noqa: F821
    evidence: Mapped[list["Evidence"]] = relationship(  # noqa: F821
        "Evidence", back_populates="case"
    )
    timeline_entries: Mapped[list["TimelineEntry"]] = relationship(  # noqa: F821
        "TimelineEntry", back_populates="case"
    )
    notes: Mapped[list["Note"]] = relationship("Note", back_populates="case")  # noqa: F821

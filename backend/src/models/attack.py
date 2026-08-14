"""AttackMapping and AttackReference models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base


class AttackMapping(Base):
    __tablename__ = "attack_mappings"
    __table_args__ = (
        CheckConstraint(
            "case_id IS NOT NULL OR observable_id IS NOT NULL OR timeline_entry_id IS NOT NULL",
            name="ck_attack_mappings_at_least_one_ref",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True
    )
    observable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("observables.id", ondelete="CASCADE"), nullable=True
    )
    timeline_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("timeline_entries.id", ondelete="CASCADE"),
        nullable=True,
    )
    tactic_id: Mapped[str] = mapped_column(String(20), nullable=False)
    technique_id: Mapped[str] = mapped_column(String(20), nullable=False)
    sub_technique_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

    # Relationships
    case: Mapped["Case | None"] = relationship("Case")  # noqa: F821
    observable: Mapped["Observable | None"] = relationship("Observable")  # noqa: F821
    timeline_entry: Mapped["TimelineEntry | None"] = relationship("TimelineEntry")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821


class AttackReference(Base):
    __tablename__ = "attack_reference"

    technique_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    tactic_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_subtechnique: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    parent_technique_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

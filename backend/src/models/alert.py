"""Alert model — OCSF 1.8.0 Detection Finding storage.

Each alert row carries:
  - The full OCSF Detection Finding document in `ocsf_payload` (JSONB).
  - A small set of denormalized columns for fast filtering and joining:
    `severity_id`, `source_product`, `finding_uid`, `title`, `message`.
  - Watari workflow state that is NOT part of OCSF: `status`
    (pending/promoted/dismissed), `dismiss_reason`, `promoted_to_case_id`,
    `dedup_key`.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Alert(BaseModel, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'promoted', 'dismissed')",
            name="ck_alerts_status",
        ),
        Index(
            "idx_alerts_dedup",
            "tenant_id",
            "dedup_key",
            postgresql_where="dedup_key IS NOT NULL",
        ),
        Index("idx_alerts_tenant_status", "tenant_id", "status"),
        Index("idx_alerts_tenant_severity_id", "tenant_id", "severity_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )

    # --- Denormalized OCSF fields (for indexing / UI list rendering) ---
    severity_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="OCSF severity_id (0-6 or 99)",
    )
    source_product: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Denormalized from ocsf_payload.metadata.product.name",
    )
    finding_uid: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Denormalized from ocsf_payload.finding_info.uid",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Denormalized from ocsf_payload.finding_info.title (or message)",
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Denormalized from ocsf_payload.message",
    )

    # --- Full OCSF document (round-tripped verbatim) ---
    ocsf_payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        doc="The full OCSF 1.8.0 Detection Finding document",
    )

    # --- Watari workflow state (not OCSF) ---
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    dismiss_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    promoted_to_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    dedup_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    promoted_case: Mapped["Case | None"] = relationship("Case")  # noqa: F821

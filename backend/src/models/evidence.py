"""Evidence model."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "type IN ('disk_image', 'memory_dump', 'log_export', 'pcap', 'document', 'other')",
            name="ck_evidence_type",
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
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_uploaded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    integrity_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    integrity_mismatch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    registered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        TS, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TS, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="evidence")  # noqa: F821
    registrar: Mapped["User"] = relationship("User")  # noqa: F821

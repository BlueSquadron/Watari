"""Observable model."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Observable(BaseModel, Base):
    __tablename__ = "observables"
    __table_args__ = (
        CheckConstraint(
            "type IN ('ip', 'domain', 'hostname', 'url', 'hash_md5', 'hash_sha1', "
            "'hash_sha256', 'email', 'filename', 'registry_key')",
            name="ck_observables_type",
        ),
        CheckConstraint(
            "tlp IN ('red', 'amber', 'green', 'clear')",
            name="ck_observables_tlp",
        ),
        Index("idx_observables_tenant_value", "tenant_id", "value"),
        Index("idx_observables_type_value", "tenant_id", "type", "value"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    tlp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_ioc: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="observables")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821
    enrichment_results: Mapped[list["EnrichmentResult"]] = relationship(  # noqa: F821
        "EnrichmentResult", back_populates="observable"
    )

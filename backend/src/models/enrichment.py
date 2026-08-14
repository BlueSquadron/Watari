"""EnrichmentSource and EnrichmentResult models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base, BaseModel


class EnrichmentSource(BaseModel, Base):
    __tablename__ = "enrichment_sources"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    supported_observable_types: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")

    # Relationships
    results: Mapped[list["EnrichmentResult"]] = relationship(
        "EnrichmentResult", back_populates="source"
    )


class EnrichmentResult(Base):
    __tablename__ = "enrichment_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'error', 'timeout')",
            name="ck_enrichment_results_status",
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
    observable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("observables.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enrichment_sources.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queried_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

    # Relationships
    observable: Mapped["Observable"] = relationship(  # noqa: F821
        "Observable", back_populates="enrichment_results"
    )
    source: Mapped["EnrichmentSource"] = relationship("EnrichmentSource", back_populates="results")

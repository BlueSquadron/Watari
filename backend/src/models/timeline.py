"""TimelineEntry and TimelineAssetLink models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base


class TimelineEntry(Base):
    __tablename__ = "timeline_entries"
    __table_args__ = (Index("idx_timeline_case_timestamp", "case_id", "event_timestamp"),)

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
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(TS, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    is_automatic: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    event_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="timeline_entries")  # noqa: F821
    actor: Mapped["User | None"] = relationship("User")  # noqa: F821
    linked_assets: Mapped[list["Asset"]] = relationship(  # noqa: F821
        "Asset",
        secondary="timeline_asset_links",
        viewonly=True,
    )


class TimelineAssetLink(Base):
    __tablename__ = "timeline_asset_links"

    timeline_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("timeline_entries.id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        primary_key=True,
    )

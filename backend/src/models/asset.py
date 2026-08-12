"""Asset model."""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Asset(BaseModel, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("case_id", "name", name="uq_assets_case_name"),
        CheckConstraint(
            "type IN ('workstation', 'server', 'network_device', 'mobile_device', "
            "'cloud_resource', 'other')",
            name="ck_assets_type",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_compromised: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_attributes: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="assets")  # noqa: F821
    creator: Mapped["User"] = relationship("User")  # noqa: F821

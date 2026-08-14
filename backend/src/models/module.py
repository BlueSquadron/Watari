"""Module and ModuleExecution models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (
        CheckConstraint(
            "type IN ('pipeline', 'processor')",
            name="ck_modules_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    entry_point: Mapped[str] = mapped_column(String(500), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    supported_evidence_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    subscribed_events: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        TS, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    executions: Mapped[list["ModuleExecution"]] = relationship(
        "ModuleExecution", back_populates="module"
    )


class ModuleExecution(Base):
    __tablename__ = "module_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_module_executions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("modules.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_event: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TS, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=func.now())

    # Relationships
    module: Mapped["Module"] = relationship("Module", back_populates="executions")

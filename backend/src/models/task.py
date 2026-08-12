"""Task model."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseModel


class Task(BaseModel, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done', 'cancelled')",
            name="ck_tasks_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="todo")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="tasks")  # noqa: F821
    assignee: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[assignee_id]
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa: F821

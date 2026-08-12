"""Note and NoteFolder models."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TS, Base, BaseModel


class NoteFolder(Base):
    __tablename__ = "note_folders"

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
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note_folders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TS, nullable=False, server_default=func.now()
    )

    # Relationships
    parent: Mapped["NoteFolder | None"] = relationship(
        "NoteFolder", remote_side="NoteFolder.id", back_populates="children"
    )
    children: Mapped[list["NoteFolder"]] = relationship(
        "NoteFolder", back_populates="parent"
    )
    notes: Mapped[list["Note"]] = relationship("Note", back_populates="folder")


class Note(BaseModel, Base):
    __tablename__ = "notes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note_folders.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="notes")  # noqa: F821
    folder: Mapped["NoteFolder | None"] = relationship("NoteFolder", back_populates="notes")
    author: Mapped["User"] = relationship("User")  # noqa: F821

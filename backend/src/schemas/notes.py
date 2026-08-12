"""Note and NoteFolder schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None
    sort_order: int = 0


class NoteFolderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_id: UUID | None = None
    sort_order: int | None = None


class NoteFolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    parent_id: UUID | None
    name: str
    sort_order: int
    created_at: datetime


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = ""
    folder_id: UUID | None = None


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content: str | None = None
    folder_id: UUID | None = None


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    folder_id: UUID | None
    title: str
    content: str
    author_id: UUID
    created_at: datetime
    updated_at: datetime


__all__ = [
    "NoteFolderCreate",
    "NoteFolderUpdate",
    "NoteFolderResponse",
    "NoteCreate",
    "NoteUpdate",
    "NoteResponse",
]

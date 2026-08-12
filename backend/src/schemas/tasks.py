"""Task schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    assignee_id: UUID | None = None
    sort_order: int = 0


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus | None = None
    assignee_id: UUID | None = None
    sort_order: int | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    assignee_id: UUID | None
    sort_order: int
    created_by: UUID
    created_at: datetime
    updated_at: datetime


__all__ = ["TaskStatus", "TaskCreate", "TaskUpdate", "TaskResponse"]

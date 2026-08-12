"""Case schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CaseSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class CaseOutcome(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    INDETERMINATE = "indeterminate"
    NOT_APPLICABLE = "not_applicable"


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: CaseSeverity
    assignee_id: UUID | None = None
    template_id: UUID | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: CaseStatus | None = None
    severity: CaseSeverity | None = None
    outcome: CaseOutcome | None = None
    assignee_id: UUID | None = None
    tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None


class CaseClose(BaseModel):
    outcome: CaseOutcome
    closing_notes: str | None = None


class CaseMerge(BaseModel):
    source_case_ids: list[UUID] = Field(min_length=1)


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_number: int
    title: str
    description: str | None
    status: CaseStatus
    severity: CaseSeverity
    outcome: CaseOutcome | None
    assignee_id: UUID | None
    template_id: UUID | None
    tags: list[str]
    custom_fields: dict[str, Any]
    merged_from: list[UUID] | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None


class CaseListFilters(BaseModel):
    status: CaseStatus | None = None
    severity: CaseSeverity | None = None
    assignee_id: UUID | None = None
    tag: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    search: str | None = None


__all__ = [
    "CaseStatus",
    "CaseSeverity",
    "CaseOutcome",
    "CaseCreate",
    "CaseUpdate",
    "CaseClose",
    "CaseMerge",
    "CaseResponse",
    "CaseListFilters",
]

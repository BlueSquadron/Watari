"""Report and ReportTemplate schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportType(StrEnum):
    INVESTIGATION = "investigation"
    ACTIVITY = "activity"


class ReportFormat(StrEnum):
    DOCX = "docx"
    MARKDOWN = "markdown"
    HTML = "html"


class ReportTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: ReportType
    format: ReportFormat
    template_content: str = Field(min_length=1)
    tag_schema: list[dict[str, Any]] = Field(default_factory=list)


class ReportTemplateUpdate(BaseModel):
    name: str | None = None
    template_content: str | None = None
    tag_schema: list[dict[str, Any]] | None = None


class ReportTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    name: str
    type: ReportType
    format: ReportFormat
    template_content: str
    tag_schema: list[dict[str, Any]]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ReportGenerateRequest(BaseModel):
    template_id: UUID
    format: ReportFormat | None = Field(
        default=None,
        description="Optional format override; defaults to template.format",
    )


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    template_id: UUID
    format: ReportFormat
    storage_path: str | None
    generated_by: UUID
    generated_at: datetime


__all__ = [
    "ReportType",
    "ReportFormat",
    "ReportTemplateCreate",
    "ReportTemplateUpdate",
    "ReportTemplateResponse",
    "ReportGenerateRequest",
    "ReportResponse",
]

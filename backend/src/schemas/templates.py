"""Case template schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaseTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    default_severity: str | None = None
    default_tags: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of task specs: {title, description?, sort_order?}",
    )
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class CaseTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_severity: str | None = None
    default_tags: list[str] | None = None
    tasks: list[dict[str, Any]] | None = None
    custom_fields: dict[str, Any] | None = None


class CaseTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None
    name: str
    description: str | None
    default_severity: str | None
    default_tags: list[str]
    tasks: list[dict[str, Any]]
    custom_fields: dict[str, Any]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


__all__ = ["CaseTemplateCreate", "CaseTemplateUpdate", "CaseTemplateResponse"]

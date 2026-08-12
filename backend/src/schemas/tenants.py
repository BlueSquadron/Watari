"""Tenant schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    settings: dict[str, Any] = Field(default_factory=dict)
    custom_fields_schema: list[dict[str, Any]] = Field(default_factory=list)


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None
    custom_fields_schema: list[dict[str, Any]] | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    settings: dict[str, Any]
    custom_fields_schema: list[dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime


__all__ = ["TenantCreate", "TenantUpdate", "TenantResponse"]

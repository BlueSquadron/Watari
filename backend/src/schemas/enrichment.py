"""Enrichment source and result schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .observables import ObservableType


class EnrichmentStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class EnrichmentSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = Field(min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)
    supported_observable_types: list[ObservableType] = Field(min_length=1)
    is_enabled: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=300)


class EnrichmentSourceUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    supported_observable_types: list[ObservableType] | None = None
    is_enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)


class EnrichmentSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    type: str
    config: dict[str, Any]
    supported_observable_types: list[str]
    is_enabled: bool
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime


class EnrichmentResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    observable_id: UUID
    source_id: UUID
    source_name: str | None = None
    status: EnrichmentStatus
    result_data: dict[str, Any] | None
    error_message: str | None
    queried_at: datetime


class EnrichmentRequest(BaseModel):
    """Request body for triggering enrichment of one or more observables."""

    observable_ids: list[UUID] = Field(min_length=1, max_length=500)
    source_ids: list[UUID] | None = Field(
        default=None, description="Limit to specific sources; default is all enabled"
    )


class EnrichmentTriggerResponse(BaseModel):
    """Response indicating enrichment jobs have been queued."""

    queued_job_ids: list[str]
    message: str = "Enrichment jobs queued for processing"


__all__ = [
    "EnrichmentStatus",
    "EnrichmentSourceCreate",
    "EnrichmentSourceUpdate",
    "EnrichmentSourceResponse",
    "EnrichmentResultResponse",
    "EnrichmentRequest",
    "EnrichmentTriggerResponse",
]

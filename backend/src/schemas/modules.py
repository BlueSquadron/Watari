"""Module and ModuleExecution schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModuleType(StrEnum):
    PIPELINE = "pipeline"
    PROCESSOR = "processor"


class ModuleExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ModuleRegister(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=50)
    type: ModuleType
    description: str | None = None
    config_schema: dict[str, Any] = Field(default_factory=dict)
    entry_point: str = Field(min_length=1, max_length=500)
    supported_evidence_types: list[str] | None = None
    subscribed_events: list[str] | None = None


class ModuleUpdate(BaseModel):
    is_enabled: bool | None = None
    config_schema: dict[str, Any] | None = None
    subscribed_events: list[str] | None = None


class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    version: str
    type: ModuleType
    description: str | None
    config_schema: dict[str, Any]
    entry_point: str
    is_enabled: bool
    supported_evidence_types: list[str] | None
    subscribed_events: list[str] | None
    installed_at: datetime
    updated_at: datetime


class ModuleExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    module_id: UUID
    tenant_id: UUID
    case_id: UUID | None
    status: ModuleExecutionStatus
    trigger_event: str | None
    config: dict[str, Any]
    result: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


__all__ = [
    "ModuleType",
    "ModuleExecutionStatus",
    "ModuleRegister",
    "ModuleUpdate",
    "ModuleResponse",
    "ModuleExecutionResponse",
]

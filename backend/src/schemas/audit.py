"""Audit log schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    action: str
    resource_type: str
    resource_id: UUID | None
    details: dict[str, Any]
    source_ip: str | None
    user_agent: str | None
    is_service_account: bool
    created_at: datetime


class AuditLogFilters(BaseModel):
    user_id: UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


__all__ = ["AuditLogResponse", "AuditLogFilters"]

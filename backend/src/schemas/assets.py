"""Asset schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetType(StrEnum):
    WORKSTATION = "workstation"
    SERVER = "server"
    NETWORK_DEVICE = "network_device"
    MOBILE_DEVICE = "mobile_device"
    CLOUD_RESOURCE = "cloud_resource"
    OTHER = "other"


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: AssetType
    ip_address: str | None = Field(default=None, max_length=45)
    domain: str | None = Field(default=None, max_length=255)
    is_compromised: bool = False
    description: str | None = None
    custom_attributes: dict[str, Any] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: AssetType | None = None
    ip_address: str | None = None
    domain: str | None = None
    is_compromised: bool | None = None
    description: str | None = None
    custom_attributes: dict[str, Any] | None = None


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    name: str
    type: AssetType
    ip_address: str | None
    domain: str | None
    is_compromised: bool
    description: str | None
    custom_attributes: dict[str, Any]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


__all__ = ["AssetType", "AssetCreate", "AssetUpdate", "AssetResponse"]

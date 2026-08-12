"""Observable schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ObservableType(StrEnum):
    IP = "ip"
    DOMAIN = "domain"
    HOSTNAME = "hostname"
    URL = "url"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    EMAIL = "email"
    FILENAME = "filename"
    REGISTRY_KEY = "registry_key"


class TLP(StrEnum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"
    CLEAR = "clear"


class ObservableCreate(BaseModel):
    type: ObservableType
    value: str = Field(min_length=1)
    tlp: TLP | None = None
    is_ioc: bool = False
    tags: list[str] = Field(default_factory=list)
    description: str | None = None


class ObservableBulkCreate(BaseModel):
    observables: list[ObservableCreate] = Field(min_length=1, max_length=1000)


class ObservableUpdate(BaseModel):
    tlp: TLP | None = None
    is_ioc: bool | None = None
    tags: list[str] | None = None
    description: str | None = None


class ObservableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    type: ObservableType
    value: str
    tlp: TLP | None
    is_ioc: bool
    tags: list[str]
    description: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    seen_in_cases_count: int | None = Field(
        default=None, description="Number of OTHER cases in the same tenant containing this observable"
    )


__all__ = [
    "ObservableType",
    "TLP",
    "ObservableCreate",
    "ObservableBulkCreate",
    "ObservableUpdate",
    "ObservableResponse",
]

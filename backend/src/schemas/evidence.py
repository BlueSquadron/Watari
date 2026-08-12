"""Evidence schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceType(StrEnum):
    DISK_IMAGE = "disk_image"
    MEMORY_DUMP = "memory_dump"
    LOG_EXPORT = "log_export"
    PCAP = "pcap"
    DOCUMENT = "document"
    OTHER = "other"


class EvidenceRegister(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    type: EvidenceType
    file_hash_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]{64}$")
    file_size: int = Field(gt=0)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class EvidenceUpdate(BaseModel):
    description: str | None = None
    tags: list[str] | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    filename: str
    type: EvidenceType
    file_hash_sha256: str
    file_size: int
    description: str | None
    storage_path: str | None
    is_uploaded: bool
    is_encrypted: bool
    integrity_verified: bool | None
    integrity_mismatch: bool
    tags: list[str]
    registered_by: UUID
    registered_at: datetime
    updated_at: datetime


class EvidenceUploadResponse(BaseModel):
    """Response after an evidence file upload completes."""

    evidence: EvidenceResponse
    integrity_verified: bool
    integrity_mismatch: bool


__all__ = [
    "EvidenceType",
    "EvidenceRegister",
    "EvidenceUpdate",
    "EvidenceResponse",
    "EvidenceUploadResponse",
]

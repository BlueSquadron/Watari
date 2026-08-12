"""MITRE ATT&CK mapping schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AttackMappingCreate(BaseModel):
    case_id: UUID | None = None
    observable_id: UUID | None = None
    timeline_entry_id: UUID | None = None
    tactic_id: str = Field(min_length=1, max_length=20)
    technique_id: str = Field(min_length=1, max_length=20)
    sub_technique_id: str | None = Field(default=None, max_length=20)


class AttackMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID | None
    observable_id: UUID | None
    timeline_entry_id: UUID | None
    tactic_id: str
    technique_id: str
    sub_technique_id: str | None
    created_by: UUID
    created_at: datetime


class AttackReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technique_id: str
    tactic_id: str
    name: str
    description: str | None
    is_subtechnique: bool
    parent_technique_id: str | None
    updated_at: datetime


class AttackHeatmapCell(BaseModel):
    """One cell of the ATT&CK heatmap — a tactic/technique pair with counts."""

    tactic_id: str
    technique_id: str
    case_count: int
    max_severity: str | None
    linked_case_ids: list[UUID] = Field(default_factory=list)


class AttackHeatmapResponse(BaseModel):
    cells: list[AttackHeatmapCell]


__all__ = [
    "AttackMappingCreate",
    "AttackMappingResponse",
    "AttackReferenceResponse",
    "AttackHeatmapCell",
    "AttackHeatmapResponse",
]

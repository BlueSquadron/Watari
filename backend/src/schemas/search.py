"""Search request/response schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SearchEntityType(StrEnum):
    CASE = "case"
    OBSERVABLE = "observable"
    ASSET = "asset"
    NOTE = "note"
    ALERT = "alert"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    entity_types: list[SearchEntityType] = Field(default_factory=lambda: list(SearchEntityType))
    limit: int = Field(default=50, ge=1, le=500)


class SearchHit(BaseModel):
    entity_type: SearchEntityType
    entity_id: UUID
    case_id: UUID | None = None
    title: str
    snippet: str
    extra: dict[str, Any] = Field(default_factory=dict)
    score: float


class SearchResponse(BaseModel):
    query: str
    total_hits: int
    hits: list[SearchHit]


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    entity_type: SearchEntityType
    filters: dict[str, Any]
    shared: bool = False


class SavedViewResponse(BaseModel):
    id: UUID
    name: str
    entity_type: SearchEntityType
    filters: dict[str, Any]
    shared: bool
    owner_id: UUID


__all__ = [
    "SearchEntityType",
    "SearchRequest",
    "SearchHit",
    "SearchResponse",
    "SavedViewCreate",
    "SavedViewResponse",
]

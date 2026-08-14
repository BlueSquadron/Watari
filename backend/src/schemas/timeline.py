"""Timeline entry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class TimelineEntryCreate(BaseModel):
    """Payload for analyst-created manual timeline entries."""

    event_type: str = Field(min_length=1, max_length=50)
    event_timestamp: datetime
    description: str = Field(min_length=1)
    category: str | None = Field(default=None, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)
    linked_asset_ids: list[UUID] = Field(default_factory=list)


class TimelineEntryUpdate(BaseModel):
    description: str | None = None
    category: str | None = None
    metadata: dict[str, Any] | None = None
    linked_asset_ids: list[UUID] | None = None


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    case_id: UUID
    event_type: str
    event_timestamp: datetime
    description: str
    category: str | None
    actor_id: UUID | None
    is_automatic: bool
    # The ORM maps the `metadata` column to `event_metadata` to avoid colliding
    # with SQLAlchemy's declarative `Base.metadata`. Validate from the attribute
    # name (a bare `alias` would resolve `metadata` to the MetaData registry),
    # but keep serializing as `metadata` so the API response shape is unchanged.
    event_metadata: dict[str, Any] = Field(
        validation_alias=AliasChoices("event_metadata", "metadata"),
        serialization_alias="metadata",
    )
    linked_asset_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class TimelineFilters(BaseModel):
    event_type: str | None = None
    category: str | None = None
    actor_id: UUID | None = None
    event_after: datetime | None = None
    event_before: datetime | None = None
    order: str = Field(default="asc", pattern="^(asc|desc)$")


class TemporalCluster(BaseModel):
    """A group of timeline entries detected as temporally clustered."""

    start: datetime
    end: datetime
    entry_ids: list[UUID]


class TimelineSwimlaneResponse(BaseModel):
    """Timeline data shaped for the swimlane visualization."""

    entries: list[TimelineEntryResponse]
    clusters: list[TemporalCluster]
    lanes: dict[str, list[UUID]] = Field(
        description="Map from lane key (asset id, analyst id, or category) to entry ids"
    )


__all__ = [
    "TimelineEntryCreate",
    "TimelineEntryUpdate",
    "TimelineEntryResponse",
    "TimelineFilters",
    "TemporalCluster",
    "TimelineSwimlaneResponse",
]

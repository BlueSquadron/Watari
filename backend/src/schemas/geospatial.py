"""Geospatial observable visualization schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .observables import ObservableType, TLP


class GeoMarker(BaseModel):
    observable_id: UUID
    case_id: UUID
    type: ObservableType
    value: str
    tlp: TLP | None
    is_ioc: bool
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    country_code: str | None = None
    city: str | None = None
    threat_score: float | None = Field(default=None, ge=0, le=100)
    last_enriched_at: datetime | None = None


class GeoResponse(BaseModel):
    markers: list[GeoMarker]


__all__ = ["GeoMarker", "GeoResponse"]

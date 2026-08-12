"""Shared base class for entity response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EntityResponseBase(BaseModel):
    """Common fields on every entity response (id + timestamps)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


__all__ = ["EntityResponseBase"]

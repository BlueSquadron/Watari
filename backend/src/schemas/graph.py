"""Case relationship graph schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GraphNodeType(StrEnum):
    CASE = "case"
    OBSERVABLE = "observable"
    ASSET = "asset"
    TIMELINE_ENTRY = "timeline_entry"


class GraphEdgeType(StrEnum):
    CONTAINS = "contains"
    LINKED_TO = "linked_to"
    CORRELATES = "correlates"


class GraphNode(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: GraphEdgeType
    label: str | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class GraphFilters(BaseModel):
    include_node_types: list[GraphNodeType] | None = None
    include_cross_case: bool = True
    date_after: str | None = None
    date_before: str | None = None


__all__ = [
    "GraphNodeType",
    "GraphEdgeType",
    "GraphNode",
    "GraphEdge",
    "GraphResponse",
    "GraphFilters",
]

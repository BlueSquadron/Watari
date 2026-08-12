"""Pydantic request and response schemas for the Watari API.

Organized by domain. Import specific types from the per-domain modules
rather than from this package root — each module defines its own
`__all__` so mypy can catch stray imports.
"""

from . import (
    alerts,
    assets,
    attack,
    audit,
    base,
    cases,
    common,
    dashboard,
    enrichment,
    evidence,
    geospatial,
    graph,
    modules,
    notes,
    observables,
    reports,
    search,
    tasks,
    templates,
    tenants,
    timeline,
    users,
)

__all__ = [
    "alerts",
    "assets",
    "attack",
    "audit",
    "base",
    "cases",
    "common",
    "dashboard",
    "enrichment",
    "evidence",
    "geospatial",
    "graph",
    "modules",
    "notes",
    "observables",
    "reports",
    "search",
    "tasks",
    "templates",
    "tenants",
    "timeline",
    "users",
]

"""Watari module (plugin) system.

Modules extend the platform with custom processing: enrichment,
evidence parsing, event-driven automation. See `base.py` for the
contract every module must implement.
"""

from .base import (
    BaseModule,
    ModuleAPI,
    ModuleRegistry,
    ModuleType,
    PlatformEvent,
    get_registry,
)

__all__ = [
    "BaseModule",
    "ModuleAPI",
    "ModuleRegistry",
    "ModuleType",
    "PlatformEvent",
    "get_registry",
]

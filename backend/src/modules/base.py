"""Base classes and registry for Watari modules (plugins).

Modules are the extensibility point: they let operators wire external
tools (threat intel feeds, EDR platforms, ticketing systems) into the
case management workflow without modifying core code.

Two flavors:
- ``PipelineModule`` — processes uploaded evidence (EVTX parsers,
  PCAP extractors, disk image triage, etc.). Triggered by users.
- ``ProcessorModule`` — reacts to platform events (observable
  created, evidence uploaded, case status changed, alert ingested)
  and performs side effects (auto-enrichment, notifications,
  external-ticket sync). Triggered by event hooks.

Both share a common ``execute`` coroutine and receive a ``ModuleAPI``
that lets them read/write case entities safely.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any
from uuid import UUID


class PlatformEvent(StrEnum):
    """Event types a processor module can subscribe to."""

    OBSERVABLE_CREATED = "observable_created"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    CASE_STATUS_CHANGED = "case_status_changed"
    ALERT_INGESTED = "alert_ingested"
    CASE_CREATED = "case_created"


class ModuleType(StrEnum):
    PIPELINE = "pipeline"
    PROCESSOR = "processor"


class ModuleAPI(ABC):
    """Interface modules use to interact with case data.

    A concrete implementation (backed by an AsyncSession + services)
    is provided at runtime by the module executor.
    """

    @abstractmethod
    async def get_case(self, case_id: UUID) -> dict[str, Any]: ...

    @abstractmethod
    async def get_observables(self, case_id: UUID) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_assets(self, case_id: UUID) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_timeline(self, case_id: UUID) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def add_observable(
        self, case_id: UUID, observable: dict[str, Any]
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def add_timeline_entry(
        self, case_id: UUID, entry: dict[str, Any]
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def add_task(
        self, case_id: UUID, task: dict[str, Any]
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def update_asset(
        self, case_id: UUID, asset_id: UUID, update: dict[str, Any]
    ) -> dict[str, Any]: ...


class BaseModule(ABC):
    """Abstract base class every module inherits from."""

    # Subclasses populate these class attributes
    name: str = ""
    version: str = "0.0.0"
    type: ModuleType = ModuleType.PROCESSOR
    description: str = ""
    config_schema: dict[str, Any] = {}
    supported_evidence_types: list[str] | None = None
    subscribed_events: list[PlatformEvent] | None = None

    @abstractmethod
    async def execute(
        self,
        context: ModuleAPI,
        config: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the module.

        Args:
            context: A ModuleAPI for reading/writing case data.
            config: Per-install configuration (matches config_schema).
            payload: Event-specific payload. For pipeline modules this
                contains ``evidence_id`` and ``case_id``. For processor
                modules it contains ``event_type`` and event-specific
                fields (e.g. observable_id for OBSERVABLE_CREATED).

        Returns:
            A JSON-serializable result dict stored on
            ``module_executions.result``.
        """


class ModuleRegistry:
    """In-process registry of module implementations.

    Keyed by ``entry_point`` (e.g. ``virustotal.enrich``). The registry
    is populated at application startup by scanning installed modules
    or via explicit ``register()`` calls. Database rows in the
    ``modules`` table reference an entry_point that MUST resolve here.
    """

    def __init__(self) -> None:
        self._modules: dict[str, type[BaseModule]] = {}

    def register(self, entry_point: str, module_cls: type[BaseModule]) -> None:
        self._modules[entry_point] = module_cls

    def get(self, entry_point: str) -> type[BaseModule] | None:
        return self._modules.get(entry_point)

    def list(self) -> list[str]:
        return sorted(self._modules.keys())


_registry = ModuleRegistry()


def get_registry() -> ModuleRegistry:
    return _registry


__all__ = [
    "BaseModule",
    "ModuleAPI",
    "ModuleRegistry",
    "ModuleType",
    "PlatformEvent",
    "get_registry",
]

"""Runtime `ModuleAPI` implementation backed by an AsyncSession.

Modules receive an instance of `SessionModuleAPI` when they execute.
All reads and writes go through the case management service layer so
timeline entries, permission checks, and validation are enforced the
same way as for user-driven requests.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.assets import AssetUpdate
from src.schemas.observables import ObservableCreate, ObservableType
from src.schemas.tasks import TaskCreate
from src.schemas.timeline import TimelineEntryCreate
from src.services import assets as asset_service
from src.services import observables as observable_service
from src.services import tasks as task_service
from src.services import timeline as timeline_service
from src.services.timeline_recorder import record_event

from .base import ModuleAPI


class SessionModuleAPI(ModuleAPI):
    """ModuleAPI bound to a given AsyncSession and acting-user id."""

    def __init__(self, db: AsyncSession, actor_id: UUID | None) -> None:
        self._db = db
        self._actor_id = actor_id

    async def get_case(self, case_id: UUID) -> dict[str, Any]:
        from sqlalchemy import select

        from src.models import Case

        row = (
            await self._db.execute(select(Case).where(Case.id == case_id))
        ).scalar_one_or_none()
        if row is None:
            return {}
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "case_number": row.case_number,
            "title": row.title,
            "status": row.status,
            "severity": row.severity,
            "tags": list(row.tags or []),
        }

    async def get_observables(self, case_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await observable_service.list_observables(
            self._db, case_id, limit=1000
        )
        return [
            {
                "id": str(o.id),
                "type": o.type,
                "value": o.value,
                "tlp": o.tlp,
                "is_ioc": o.is_ioc,
            }
            for o in rows
        ]

    async def get_assets(self, case_id: UUID) -> list[dict[str, Any]]:
        rows, _ = await asset_service.list_assets(self._db, case_id, limit=1000)
        return [
            {
                "id": str(a.id),
                "name": a.name,
                "type": a.type,
                "ip_address": a.ip_address,
                "is_compromised": a.is_compromised,
            }
            for a in rows
        ]

    async def get_timeline(self, case_id: UUID) -> list[dict[str, Any]]:
        from src.schemas.timeline import TimelineFilters

        rows, _ = await timeline_service.list_entries(
            self._db, case_id, TimelineFilters(order="asc"), limit=1000
        )
        return [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "event_timestamp": e.event_timestamp.isoformat(),
                "description": e.description,
            }
            for e in rows
        ]

    async def add_observable(
        self, case_id: UUID, observable: dict[str, Any]
    ) -> dict[str, Any]:
        payload = ObservableCreate(
            type=ObservableType(observable["type"]),
            value=observable["value"],
            tlp=observable.get("tlp"),
            is_ioc=bool(observable.get("is_ioc", False)),
            tags=list(observable.get("tags", [])),
            description=observable.get("description"),
        )
        created = await observable_service.create_observable(
            self._db,
            case_id=case_id,
            created_by=self._actor_id or UUID(int=0),
            payload=payload,
        )
        return {"id": str(created.id), "value": created.value, "type": created.type}

    async def add_timeline_entry(
        self, case_id: UUID, entry: dict[str, Any]
    ) -> dict[str, Any]:
        # Modules can choose to write a "manual" entry OR an automatic event.
        if entry.get("is_automatic", True):
            row = await record_event(
                self._db,
                tenant_id=UUID(entry["tenant_id"])
                if "tenant_id" in entry
                else (await self._resolve_tenant(case_id)),
                case_id=case_id,
                event_type=entry.get("event_type", "module"),
                description=entry.get("description", ""),
                category=entry.get("category", "module"),
                actor_id=self._actor_id,
                metadata=entry.get("metadata") or {},
            )
            return {"id": str(row.id)}

        from datetime import UTC, datetime

        payload = TimelineEntryCreate(
            event_type=entry.get("event_type", "module"),
            event_timestamp=datetime.fromisoformat(
                entry.get("event_timestamp", datetime.now(UTC).isoformat())
            ),
            description=entry.get("description", ""),
            category=entry.get("category"),
            metadata=entry.get("metadata") or {},
        )
        row = await timeline_service.create_manual_entry(
            self._db,
            case_id=case_id,
            actor_id=self._actor_id or UUID(int=0),
            payload=payload,
        )
        return {"id": str(row.id)}

    async def add_task(
        self, case_id: UUID, task: dict[str, Any]
    ) -> dict[str, Any]:
        payload = TaskCreate(
            title=task["title"],
            description=task.get("description"),
            sort_order=task.get("sort_order", 0),
        )
        created = await task_service.create_task(
            self._db,
            case_id=case_id,
            created_by=self._actor_id or UUID(int=0),
            payload=payload,
        )
        return {"id": str(created.id), "title": created.title}

    async def update_asset(
        self, case_id: UUID, asset_id: UUID, update: dict[str, Any]
    ) -> dict[str, Any]:
        payload = AssetUpdate(**update)
        row = await asset_service.update_asset(
            self._db,
            asset_id,
            payload,
            actor_id=self._actor_id or UUID(int=0),
        )
        return {"id": str(row.id), "is_compromised": row.is_compromised}

    async def _resolve_tenant(self, case_id: UUID) -> UUID:
        from sqlalchemy import select

        from src.models import Case

        tid = (
            await self._db.execute(select(Case.tenant_id).where(Case.id == case_id))
        ).scalar_one()
        return tid  # type: ignore[return-value]


__all__ = ["SessionModuleAPI"]

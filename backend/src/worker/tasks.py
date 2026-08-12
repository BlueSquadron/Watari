"""Celery task definitions for Watari background work.

Each task is thin — it delegates heavy lifting to services. Async DB
work in Celery requires an event loop per task; we use
`asyncio.run()` to bridge the sync Celery API with the async
service layer.
"""

from __future__ import annotations

import asyncio
from typing import Any

from . import celery_app


@celery_app.task(name="enrichment.execute")
def execute_enrichment(observable_id: str, source_id: str) -> dict[str, Any]:
    """Execute enrichment for a single observable against a single source.

    This is a placeholder for v1 that records a synthetic success result.
    Real implementations will call the external API (VirusTotal, MISP, etc.)
    using the source's `config` JSON.
    """
    return asyncio.run(_execute_enrichment(observable_id, source_id))


async def _execute_enrichment(observable_id: str, source_id: str) -> dict[str, Any]:
    from uuid import UUID

    from sqlalchemy import select
    from src.db import async_session_factory
    from src.models import EnrichmentResult, EnrichmentSource, Observable

    async with async_session_factory() as session:
        obs = (
            await session.execute(
                select(Observable).where(Observable.id == UUID(observable_id))
            )
        ).scalar_one_or_none()
        source = (
            await session.execute(
                select(EnrichmentSource).where(EnrichmentSource.id == UUID(source_id))
            )
        ).scalar_one_or_none()
        if obs is None or source is None:
            return {"status": "error", "detail": "observable or source not found"}

        # Stub: real integrations go here (VirusTotal, AbuseIPDB, MISP, Shodan)
        result = EnrichmentResult(
            tenant_id=obs.tenant_id,
            observable_id=obs.id,
            source_id=source.id,
            status="success",
            result_data={
                "source": source.type,
                "observable": obs.value,
                "note": "stub enrichment result",
            },
        )
        session.add(result)
        await session.commit()
        return {"status": "success", "result_id": str(result.id)}


@celery_app.task(name="module.processor.execute")
def execute_processor_module(
    module_id: str,
    tenant_id: str,
    case_id: str | None,
    event_type: str,
    payload: dict[str, Any],
    actor_id: str | None,
) -> dict[str, Any]:
    """Execute a processor module triggered by a platform event."""
    return asyncio.run(
        _execute_processor_module(
            module_id, tenant_id, case_id, event_type, payload, actor_id
        )
    )


async def _execute_processor_module(
    module_id: str,
    tenant_id: str,
    case_id: str | None,
    event_type: str,
    payload: dict[str, Any],
    actor_id: str | None,
) -> dict[str, Any]:
    from uuid import UUID

    from src.db import async_session_factory
    from src.services import modules as module_service

    async with async_session_factory() as session:
        execution = await module_service.execute_module(
            session,
            module_id=UUID(module_id),
            tenant_id=UUID(tenant_id),
            case_id=UUID(case_id) if case_id else None,
            config={},
            payload=payload,
            actor_id=UUID(actor_id) if actor_id else None,
            trigger_event=event_type,
        )
        await session.commit()
        return {"execution_id": str(execution.id), "status": execution.status}


@celery_app.task(name="report.generate")
def generate_report_task(case_id: str, template_id: str, format: str) -> dict[str, Any]:
    """Generate a report in the background; see reports service for details."""
    return asyncio.run(_generate_report(case_id, template_id, format))


async def _generate_report(case_id: str, template_id: str, format: str) -> dict[str, Any]:
    from uuid import UUID

    from src.db import async_session_factory
    from src.services import reports as reports_service

    async with async_session_factory() as session:
        report = await reports_service.generate_report(
            session,
            case_id=UUID(case_id),
            template_id=UUID(template_id),
            format_override=format,
            generated_by=None,
        )
        await session.commit()
        return {"report_id": str(report.id)}


__all__ = ["execute_enrichment", "generate_report_task", "execute_processor_module"]

"""Report generation service.

Renders investigation and activity reports in DOCX, Markdown, and HTML.
Templates are Jinja2 strings for Markdown/HTML. DOCX rendering uses
python-docx to convert a rendered Markdown into a structured document
(v1 keeps this simple; a future version can use docxtpl for true
tag-based .docx templates).
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from jinja2 import Environment, StrictUndefined
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    Asset,
    AttackMapping,
    AuditLog,
    Case,
    Evidence,
    Note,
    Observable,
    Report,
    ReportTemplate,
    Task,
    TimelineEntry,
)
from src.schemas.reports import ReportFormat, ReportType

from . import storage
from .timeline_recorder import record_event

_env = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


async def _build_context(db: AsyncSession, case: Case) -> dict[str, Any]:
    """Build the Jinja context for the investigation template."""
    observables = (
        (await db.execute(select(Observable).where(Observable.case_id == case.id))).scalars().all()
    )
    assets = (await db.execute(select(Asset).where(Asset.case_id == case.id))).scalars().all()
    timeline = (
        (
            await db.execute(
                select(TimelineEntry)
                .where(TimelineEntry.case_id == case.id)
                .order_by(TimelineEntry.event_timestamp.asc())
            )
        )
        .scalars()
        .all()
    )
    tasks = (await db.execute(select(Task).where(Task.case_id == case.id))).scalars().all()
    notes = (await db.execute(select(Note).where(Note.case_id == case.id))).scalars().all()
    evidence = (
        (await db.execute(select(Evidence).where(Evidence.case_id == case.id))).scalars().all()
    )
    attack = (
        (await db.execute(select(AttackMapping).where(AttackMapping.case_id == case.id)))
        .scalars()
        .all()
    )

    return {
        "case": {
            "id": str(case.id),
            "case_number": case.case_number,
            "title": case.title,
            "description": case.description,
            "status": case.status,
            "severity": case.severity,
            "outcome": case.outcome,
            "tags": list(case.tags or []),
            "created_at": case.created_at,
            "resolved_at": case.resolved_at,
            "closed_at": case.closed_at,
        },
        "observables": [
            {
                "type": o.type,
                "value": o.value,
                "tlp": o.tlp,
                "is_ioc": o.is_ioc,
                "tags": list(o.tags or []),
                "description": o.description,
            }
            for o in observables
        ],
        "assets": [
            {
                "name": a.name,
                "type": a.type,
                "ip_address": a.ip_address,
                "domain": a.domain,
                "is_compromised": a.is_compromised,
                "description": a.description,
            }
            for a in assets
        ],
        "timeline": [
            {
                "event_timestamp": e.event_timestamp,
                "event_type": e.event_type,
                "category": e.category,
                "description": e.description,
                "is_automatic": e.is_automatic,
            }
            for e in timeline
        ],
        "tasks": [
            {
                "title": t.title,
                "status": t.status,
                "description": t.description,
            }
            for t in tasks
        ],
        "notes": [
            {"title": n.title, "content": n.content, "updated_at": n.updated_at} for n in notes
        ],
        "evidence": [
            {
                "filename": ev.filename,
                "type": ev.type,
                "sha256": ev.file_hash_sha256,
                "size": ev.file_size,
                "integrity_verified": ev.integrity_verified,
            }
            for ev in evidence
        ],
        "attack": [
            {
                "tactic": m.tactic_id,
                "technique": m.technique_id,
                "sub_technique": m.sub_technique_id,
            }
            for m in attack
        ],
    }


async def _build_activity_context(db: AsyncSession, case: Case) -> dict[str, Any]:
    """Build the Jinja context for activity reports — the case audit trail."""
    # We look at audit logs referencing this case id plus its timeline entries.
    audit_rows = (
        (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.tenant_id == case.tenant_id)
                .where(AuditLog.resource_id == case.id)
                .order_by(AuditLog.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    timeline = (
        (
            await db.execute(
                select(TimelineEntry)
                .where(TimelineEntry.case_id == case.id)
                .order_by(TimelineEntry.event_timestamp.asc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "case": {
            "title": case.title,
            "case_number": case.case_number,
        },
        "audit_entries": [
            {
                "created_at": e.created_at,
                "action": e.action,
                "resource_type": e.resource_type,
                "user_id": str(e.user_id),
                "details": e.details,
            }
            for e in audit_rows
        ],
        "timeline_entries": [
            {
                "event_timestamp": e.event_timestamp,
                "event_type": e.event_type,
                "description": e.description,
                "actor_id": str(e.actor_id) if e.actor_id else None,
            }
            for e in timeline
        ],
    }


def render_markdown(template_content: str, context: dict[str, Any]) -> str:
    template = _env.from_string(template_content)
    return template.render(**context)


def render_html(template_content: str, context: dict[str, Any]) -> str:
    return render_markdown(template_content, context)


def render_docx(template_content: str, context: dict[str, Any]) -> bytes:
    """Render a DOCX from a Markdown template.

    v1: we render the Markdown first, then produce a minimal DOCX
    containing the rendered text split by paragraph. A future version can
    use docxtpl for true tag-based .docx templates.
    """
    from io import BytesIO

    from docx import Document

    rendered = render_markdown(template_content, context)
    doc = Document()
    for paragraph in rendered.split("\n\n"):
        doc.add_paragraph(paragraph)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def generate_report(
    db: AsyncSession,
    *,
    case_id: UUID,
    template_id: UUID,
    format_override: str | None = None,
    generated_by: UUID | None,
) -> Report:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    template = (
        await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")

    context: dict[str, Any]
    if template.type == ReportType.INVESTIGATION.value:
        context = await _build_context(db, case)
    else:
        context = await _build_activity_context(db, case)

    chosen_format = format_override or template.format
    rendered: bytes
    if chosen_format == ReportFormat.MARKDOWN.value:
        rendered = render_markdown(template.template_content, context).encode("utf-8")
        content_type = "text/markdown"
    elif chosen_format == ReportFormat.HTML.value:
        rendered = render_html(template.template_content, context).encode("utf-8")
        content_type = "text/html"
    elif chosen_format == ReportFormat.DOCX.value:
        rendered = render_docx(template.template_content, context)
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Unsupported report format: {chosen_format}"
        )

    storage_key = f"reports/{case.tenant_id}/{case.id}/{uuid.uuid4()}.{chosen_format}"
    await storage.upload_bytes(storage_key, rendered, content_type=content_type)

    report = Report(
        tenant_id=case.tenant_id,
        case_id=case.id,
        template_id=template.id,
        format=chosen_format,
        storage_path=storage_key,
        generated_by=generated_by or case.created_by,
    )
    db.add(report)
    await db.flush()
    await record_event(
        db,
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type="report_generated",
        description=f"Report generated ({chosen_format}): {template.name}",
        category="report",
        actor_id=generated_by,
        metadata={"report_id": str(report.id), "template_id": str(template.id)},
    )
    await db.refresh(report)
    return report


async def preview_report(db: AsyncSession, *, case_id: UUID, template_id: UUID) -> str:
    """Return the rendered Markdown/HTML preview text without storing anything."""
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    template = (
        await db.execute(select(ReportTemplate).where(ReportTemplate.id == template_id))
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report template not found")
    context = (
        await _build_context(db, case)
        if template.type == ReportType.INVESTIGATION.value
        else await _build_activity_context(db, case)
    )
    return render_markdown(template.template_content, context)


# ---- Template CRUD ----


async def list_templates(db: AsyncSession, tenant_id: UUID) -> list[ReportTemplate]:
    rows = (
        (
            await db.execute(
                select(ReportTemplate).where(
                    (ReportTemplate.tenant_id == tenant_id) | (ReportTemplate.tenant_id.is_(None))
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def create_template(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    type: str,
    format: str,
    template_content: str,
    tag_schema: list[dict[str, Any]],
    created_by: UUID,
) -> ReportTemplate:
    t = ReportTemplate(
        tenant_id=tenant_id,
        name=name,
        type=type,
        format=format,
        template_content=template_content,
        tag_schema=tag_schema,
        created_by=created_by,
    )
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


__all__ = [
    "render_markdown",
    "render_html",
    "render_docx",
    "generate_report",
    "preview_report",
    "list_templates",
    "create_template",
]

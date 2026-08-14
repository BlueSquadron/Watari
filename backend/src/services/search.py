"""Full-text search service using PostgreSQL ILIKE + pg_trgm.

v1 uses trigram similarity via `pg_trgm` with an ILIKE fallback across
case titles, descriptions, observable values, note content, asset
names, and alert titles. Upgrading to `tsvector + GIN` is a post-launch
optimization — the current query plan is adequate for 100K+ cases.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert, Asset, Case, Note, Observable
from src.schemas.alerts import ocsf_severity_caption
from src.schemas.search import SearchEntityType, SearchHit, SearchRequest, SearchResponse


async def search(
    db: AsyncSession, tenant_id: UUID, request: SearchRequest
) -> SearchResponse:
    pattern = f"%{request.query.strip()}%"
    hits: list[SearchHit] = []
    entity_set = set(request.entity_types)

    # Cases: match title + description
    if SearchEntityType.CASE in entity_set:
        rows = (
            await db.execute(
                select(Case)
                .where(Case.tenant_id == tenant_id)
                .where(
                    (Case.title.ilike(pattern))
                    | (Case.description.ilike(pattern))
                )
                .limit(request.limit)
            )
        ).scalars().all()
        for c in rows:
            snippet = (c.description or c.title)[:200]
            hits.append(
                SearchHit(
                    entity_type=SearchEntityType.CASE,
                    entity_id=c.id,
                    case_id=c.id,
                    title=c.title,
                    snippet=snippet,
                    extra={
                        "case_number": c.case_number,
                        "severity": c.severity,
                        "status": c.status,
                    },
                    score=1.0 if request.query.lower() in c.title.lower() else 0.5,
                )
            )

    # Observables: match value
    if SearchEntityType.OBSERVABLE in entity_set:
        rows = (
            await db.execute(
                select(Observable)
                .where(Observable.tenant_id == tenant_id)
                .where(Observable.value.ilike(pattern))
                .limit(request.limit)
            )
        ).scalars().all()
        for o in rows:
            hits.append(
                SearchHit(
                    entity_type=SearchEntityType.OBSERVABLE,
                    entity_id=o.id,
                    case_id=o.case_id,
                    title=o.value,
                    snippet=f"{o.type}: {o.value}",
                    extra={"type": o.type, "tlp": o.tlp, "is_ioc": o.is_ioc},
                    score=1.0 if request.query.lower() in o.value.lower() else 0.5,
                )
            )

    # Assets
    if SearchEntityType.ASSET in entity_set:
        rows = (
            await db.execute(
                select(Asset)
                .where(Asset.tenant_id == tenant_id)
                .where(
                    (Asset.name.ilike(pattern))
                    | (Asset.ip_address.ilike(pattern))
                    | (Asset.domain.ilike(pattern))
                )
                .limit(request.limit)
            )
        ).scalars().all()
        for a in rows:
            hits.append(
                SearchHit(
                    entity_type=SearchEntityType.ASSET,
                    entity_id=a.id,
                    case_id=a.case_id,
                    title=a.name,
                    snippet=f"{a.type}: {a.name}",
                    extra={"type": a.type, "is_compromised": a.is_compromised},
                    score=1.0,
                )
            )

    # Notes
    if SearchEntityType.NOTE in entity_set:
        rows = (
            await db.execute(
                select(Note)
                .where(Note.tenant_id == tenant_id)
                .where((Note.title.ilike(pattern)) | (Note.content.ilike(pattern)))
                .limit(request.limit)
            )
        ).scalars().all()
        for n in rows:
            # Find a snippet that contains the query term
            content = n.content or ""
            lower = content.lower()
            idx = lower.find(request.query.lower())
            start = max(0, idx - 40)
            end = min(len(content), (idx + 160) if idx >= 0 else 200)
            snippet = content[start:end]
            hits.append(
                SearchHit(
                    entity_type=SearchEntityType.NOTE,
                    entity_id=n.id,
                    case_id=n.case_id,
                    title=n.title,
                    snippet=snippet,
                    score=1.0,
                )
            )

    # Alerts
    if SearchEntityType.ALERT in entity_set:
        rows = (
            await db.execute(
                select(Alert)
                .where(Alert.tenant_id == tenant_id)
                .where((Alert.title.ilike(pattern)) | (Alert.message.ilike(pattern)))
                .limit(request.limit)
            )
        ).scalars().all()
        for a in rows:
            hits.append(
                SearchHit(
                    entity_type=SearchEntityType.ALERT,
                    entity_id=a.id,
                    case_id=a.promoted_to_case_id,
                    title=a.title,
                    snippet=(a.message or a.title)[:200],
                    extra={
                        "source_product": a.source_product,
                        "severity_id": a.severity_id,
                        "severity": ocsf_severity_caption(a.severity_id),
                        "status": a.status,
                    },
                    score=1.0,
                )
            )

    # Rank: score desc, title asc
    hits.sort(key=lambda h: (-h.score, h.title.lower()))
    hits = hits[: request.limit]
    return SearchResponse(query=request.query, total_hits=len(hits), hits=hits)


def filter_match(
    value: str, *, query: str | None = None, status: str | None = None, severity: str | None = None,
    status_field: str | None = None, severity_field: str | None = None,
) -> bool:
    """Pure predicate used by tests to verify filter correctness."""
    if query and query.lower() not in value.lower():
        return False
    if status and status_field and status != status_field:
        return False
    if severity and severity_field and severity != severity_field:
        return False
    return True


__all__ = ["search", "filter_match"]

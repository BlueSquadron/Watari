"""Case template service layer.

CRUD operations for `CaseTemplate`. Templates are tenant-scoped: each
tenant manages its own set of reusable case structures (phishing,
malware, data breach, etc.). When a case is created with
`template_id`, the template's tags, custom fields, severity default,
and task list are applied by `services.cases.create_case`.

The service runs under the tenant-scoped DB session so Row-Level
Security ensures callers can only see their own tenant's templates.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.template import CaseTemplate
from src.schemas.templates import CaseTemplateCreate, CaseTemplateUpdate


async def list_templates(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CaseTemplate], int]:
    """List case templates for a tenant with pagination."""
    total = (
        await db.execute(
            select(func.count())
            .select_from(CaseTemplate)
            .where(CaseTemplate.tenant_id == tenant_id)
        )
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(CaseTemplate)
                .where(CaseTemplate.tenant_id == tenant_id)
                .order_by(CaseTemplate.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def get_template(db: AsyncSession, *, tenant_id: UUID, template_id: UUID) -> CaseTemplate:
    """Fetch a template or raise 404."""
    template = (
        await db.execute(
            select(CaseTemplate).where(
                CaseTemplate.id == template_id,
                CaseTemplate.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case template {template_id} not found",
        )
    return template


async def create_template(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    created_by: UUID,
    payload: CaseTemplateCreate,
) -> CaseTemplate:
    """Create a new case template."""
    template = CaseTemplate(
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        default_severity=payload.default_severity,
        default_tags=list(payload.default_tags),
        tasks=list(payload.tasks),
        custom_fields=dict(payload.custom_fields),
        created_by=created_by,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


async def update_template(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    template_id: UUID,
    payload: CaseTemplateUpdate,
) -> CaseTemplate:
    """Apply a partial update to a template."""
    template = await get_template(db, tenant_id=tenant_id, template_id=template_id)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    await db.flush()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, *, tenant_id: UUID, template_id: UUID) -> None:
    """Delete a template. Cases already created from it keep their
    `template_id` reference, which becomes a dangling pointer. This is
    intentional — historic cases should continue to remember which
    template they came from even after the template is retired.
    """
    template = await get_template(db, tenant_id=tenant_id, template_id=template_id)
    await db.delete(template)
    await db.flush()


__all__ = [
    "list_templates",
    "get_template",
    "create_template",
    "update_template",
    "delete_template",
]

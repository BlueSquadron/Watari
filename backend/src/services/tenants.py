"""Tenant service layer.

Business logic for creating and modifying tenants. Runs under an
unscoped DB session because tenant-wide operations are platform-admin
only and need to bypass RLS.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Tenant
from src.schemas.tenants import TenantCreate, TenantUpdate


async def create_tenant(db: AsyncSession, payload: TenantCreate) -> Tenant:
    """Create a new tenant. Raises 409 if the slug already exists."""
    existing = (
        await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{payload.slug}' already exists",
        )

    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        settings=payload.settings,
        custom_fields_schema=payload.custom_fields_schema,
    )
    db.add(tenant)
    await db.flush()
    await db.refresh(tenant)
    return tenant


async def list_tenants(
    db: AsyncSession,
    *,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Tenant], int]:
    """List all tenants with pagination. Returns (rows, total_count)."""
    total = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
    rows = (
        (
            await db.execute(
                select(Tenant).order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def get_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    """Fetch a tenant by id or raise 404."""
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    return tenant


async def update_tenant(db: AsyncSession, tenant_id: UUID, payload: TenantUpdate) -> Tenant:
    """Apply a partial update to a tenant."""
    tenant = await get_tenant(db, tenant_id)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)
    await db.flush()
    await db.refresh(tenant)
    return tenant


async def delete_tenant(db: AsyncSession, tenant_id: UUID) -> None:
    """Delete a tenant. Cascades to all tenant-scoped rows via FK constraints.

    v1 permits hard delete only from platform admin; v2 may soft-delete
    via `is_active=False` instead.
    """
    tenant = await get_tenant(db, tenant_id)
    await db.delete(tenant)
    await db.flush()


__all__ = [
    "create_tenant",
    "list_tenants",
    "get_tenant",
    "update_tenant",
    "delete_tenant",
]

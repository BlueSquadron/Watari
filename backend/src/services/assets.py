"""Asset service layer."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Asset, Case
from src.schemas.assets import AssetCreate, AssetUpdate

from .timeline_recorder import record_event


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found")
    return case


async def _get_asset_or_404(db: AsyncSession, asset_id: UUID) -> Asset:
    asset = (await db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Asset {asset_id} not found")
    return asset


async def list_assets(
    db: AsyncSession, case_id: UUID, *, limit: int = 100, offset: int = 0
) -> tuple[list[Asset], int]:
    base = select(Asset).where(Asset.case_id == case_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(Asset.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)


async def create_asset(
    db: AsyncSession, *, case_id: UUID, created_by: UUID, payload: AssetCreate
) -> Asset:
    case = await _get_case_or_404(db, case_id)
    asset = Asset(
        tenant_id=case.tenant_id,
        case_id=case.id,
        name=payload.name,
        type=payload.type.value,
        ip_address=payload.ip_address,
        domain=payload.domain,
        is_compromised=payload.is_compromised,
        description=payload.description,
        custom_attributes=payload.custom_attributes,
        created_by=created_by,
    )
    # Flush inside a savepoint: a unique-constraint violation aborts the
    # surrounding transaction, and callers that handle the 409 (or share a
    # session across operations) need it to stay usable afterwards.
    try:
        async with db.begin_nested():
            db.add(asset)
            await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Asset with name '{payload.name}' already exists in this case",
        ) from exc
    await record_event(
        db,
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type="asset_added",
        description=f"Asset added: {asset.name} ({asset.type})",
        category="asset",
        actor_id=created_by,
        metadata={"asset_id": str(asset.id), "name": asset.name},
    )
    await db.refresh(asset)
    return asset


async def update_asset(
    db: AsyncSession, asset_id: UUID, payload: AssetUpdate, *, actor_id: UUID
) -> Asset:
    asset = await _get_asset_or_404(db, asset_id)
    old_compromised = asset.is_compromised
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "type" and value is not None:
            setattr(asset, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(asset, key, value)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Asset name must be unique within a case",
        ) from exc
    # Record compromise status change
    if "is_compromised" in data and asset.is_compromised != old_compromised:
        await record_event(
            db,
            tenant_id=asset.tenant_id,
            case_id=asset.case_id,
            event_type="asset_compromise_changed",
            description=(
                f"Asset '{asset.name}' marked "
                f"{'compromised' if asset.is_compromised else 'not compromised'}"
            ),
            category="asset",
            actor_id=actor_id,
            metadata={"asset_id": str(asset.id), "is_compromised": asset.is_compromised},
        )
    await db.refresh(asset)
    return asset


async def delete_asset(db: AsyncSession, asset_id: UUID) -> None:
    asset = await _get_asset_or_404(db, asset_id)
    await db.delete(asset)
    await db.flush()


async def search_assets_in_tenant(
    db: AsyncSession, tenant_id: UUID, query: str, *, limit: int = 50
) -> list[Asset]:
    pattern = f"%{query}%"
    rows = (
        await db.execute(
            select(Asset)
            .where(Asset.tenant_id == tenant_id)
            .where((Asset.name.ilike(pattern)) | (Asset.ip_address.ilike(pattern)))
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


__all__ = [
    "list_assets",
    "create_asset",
    "update_asset",
    "delete_asset",
    "search_assets_in_tenant",
]

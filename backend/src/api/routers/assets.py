"""Asset endpoints (scoped under a case)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.assets import AssetCreate, AssetResponse, AssetUpdate
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.services import assets as asset_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/assets", tags=["assets"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[AssetResponse]])
async def list_assets(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ASSET, Action.READ))],
) -> ApiResponse[list[AssetResponse]]:
    _check(auth, tenant_id)
    rows, total = await asset_service.list_assets(
        db, case_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[AssetResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post("", response_model=ApiResponse[AssetResponse], status_code=status.HTTP_201_CREATED)
async def create_asset(
    tenant_id: UUID,
    case_id: UUID,
    payload: AssetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ASSET, Action.CREATE))],
) -> ApiResponse[AssetResponse]:
    _check(auth, tenant_id)
    asset = await asset_service.create_asset(
        db, case_id=case_id, created_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=AssetResponse.model_validate(asset))


@router.patch("/{asset_id}", response_model=ApiResponse[AssetResponse])
async def update_asset(
    tenant_id: UUID,
    case_id: UUID,
    asset_id: UUID,
    payload: AssetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ASSET, Action.UPDATE))],
) -> ApiResponse[AssetResponse]:
    _check(auth, tenant_id)
    asset = await asset_service.update_asset(db, asset_id, payload, actor_id=auth.user_id)
    return ApiResponse(data=AssetResponse.model_validate(asset))


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    tenant_id: UUID,
    case_id: UUID,
    asset_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ASSET, Action.DELETE))],
) -> None:
    _check(auth, tenant_id)
    await asset_service.delete_asset(db, asset_id)


__all__ = ["router"]

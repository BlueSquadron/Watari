"""ATT&CK mapping endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.attack import (
    AttackHeatmapResponse,
    AttackMappingCreate,
    AttackMappingResponse,
    AttackReferenceResponse,
)
from src.schemas.common import ApiResponse
from src.services import attack as attack_service

mappings_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/attack-mappings", tags=["attack"]
)

reference_router = APIRouter(prefix="/api/v1/attack-reference", tags=["attack"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@mappings_router.post(
    "",
    response_model=ApiResponse[AttackMappingResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    tenant_id: UUID,
    payload: AttackMappingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ATTACK_MAPPING, Action.CREATE))
    ],
) -> ApiResponse[AttackMappingResponse]:
    _check(auth, tenant_id)
    mapping = await attack_service.create_mapping(
        db, tenant_id, payload, created_by=auth.user_id
    )
    return ApiResponse(data=AttackMappingResponse.model_validate(mapping))


@mappings_router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    tenant_id: UUID,
    mapping_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ATTACK_MAPPING, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await attack_service.delete_mapping(db, mapping_id)


@mappings_router.get("/heatmap", response_model=ApiResponse[AttackHeatmapResponse])
async def heatmap(
    tenant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ATTACK_MAPPING, Action.READ))
    ],
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    case_severity: str | None = None,
    case_status: str | None = None,
) -> ApiResponse[AttackHeatmapResponse]:
    _check(auth, tenant_id)
    cells = await attack_service.build_heatmap(
        db,
        tenant_id,
        created_after=created_after,
        created_before=created_before,
        case_severity=case_severity,
        case_status=case_status,
    )
    return ApiResponse(data=AttackHeatmapResponse(cells=cells))


@reference_router.get("", response_model=ApiResponse[list[AttackReferenceResponse]])
async def list_reference(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[list[AttackReferenceResponse]]:
    rows = await attack_service.list_reference(db)
    return ApiResponse(data=[AttackReferenceResponse.model_validate(r) for r in rows])


__all__ = ["mappings_router", "reference_router"]

"""Search endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse
from src.schemas.search import SearchRequest, SearchResponse
from src.services import search as search_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/search", tags=["search"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.post("", response_model=ApiResponse[SearchResponse])
async def search(
    tenant_id: UUID,
    payload: SearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.SEARCH, Action.READ))
    ],
) -> ApiResponse[SearchResponse]:
    _check(auth, tenant_id)
    result = await search_service.search(db, tenant_id, payload)
    return ApiResponse(data=result)


__all__ = ["router"]

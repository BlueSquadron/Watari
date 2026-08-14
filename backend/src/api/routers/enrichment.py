"""Enrichment endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.enrichment import (
    EnrichmentRequest,
    EnrichmentResultResponse,
    EnrichmentSourceCreate,
    EnrichmentSourceResponse,
    EnrichmentSourceUpdate,
    EnrichmentTriggerResponse,
)
from src.services import enrichment as enrichment_service

sources_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/enrichment-sources", tags=["enrichment"]
)

results_router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/observables/{observable_id}/enrichment",
    tags=["enrichment"],
)

trigger_router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/enrichment", tags=["enrichment"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


# --- Source management ---------------------------------------------------


@sources_router.get("", response_model=ApiResponse[list[EnrichmentSourceResponse]])
async def list_sources(
    tenant_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ENRICHMENT_SOURCE, Action.READ))
    ],
) -> ApiResponse[list[EnrichmentSourceResponse]]:
    _check(auth, tenant_id)
    rows, total = await enrichment_service.list_sources(
        db, tenant_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[EnrichmentSourceResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@sources_router.post(
    "",
    response_model=ApiResponse[EnrichmentSourceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    tenant_id: UUID,
    payload: EnrichmentSourceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ENRICHMENT_SOURCE, Action.CREATE))
    ],
) -> ApiResponse[EnrichmentSourceResponse]:
    _check(auth, tenant_id)
    src = await enrichment_service.create_source(db, tenant_id, payload)
    return ApiResponse(data=EnrichmentSourceResponse.model_validate(src))


@sources_router.patch("/{source_id}", response_model=ApiResponse[EnrichmentSourceResponse])
async def update_source(
    tenant_id: UUID,
    source_id: UUID,
    payload: EnrichmentSourceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ENRICHMENT_SOURCE, Action.UPDATE))
    ],
) -> ApiResponse[EnrichmentSourceResponse]:
    _check(auth, tenant_id)
    src = await enrichment_service.update_source(db, source_id, payload)
    return ApiResponse(data=EnrichmentSourceResponse.model_validate(src))


@sources_router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    tenant_id: UUID,
    source_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.ENRICHMENT_SOURCE, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await enrichment_service.delete_source(db, source_id)


# --- Enrichment trigger -------------------------------------------------


@trigger_router.post("", response_model=ApiResponse[EnrichmentTriggerResponse])
async def trigger(
    tenant_id: UUID,
    payload: EnrichmentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ENRICHMENT, Action.EXECUTE))],
) -> ApiResponse[EnrichmentTriggerResponse]:
    _check(auth, tenant_id)
    job_ids = await enrichment_service.trigger_enrichment(
        db, tenant_id, payload, actor_id=auth.user_id
    )
    return ApiResponse(data=EnrichmentTriggerResponse(queued_job_ids=job_ids))


# --- Enrichment results for a specific observable ----------------------


@results_router.get("", response_model=ApiResponse[list[EnrichmentResultResponse]])
async def list_observable_results(
    tenant_id: UUID,
    case_id: UUID,
    observable_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.ENRICHMENT, Action.READ))],
) -> ApiResponse[list[EnrichmentResultResponse]]:
    _check(auth, tenant_id)
    rows, total = await enrichment_service.list_results(
        db, observable_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[EnrichmentResultResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


__all__ = ["sources_router", "results_router", "trigger_router"]

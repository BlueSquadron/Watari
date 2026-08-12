"""Observable endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.observables import (
    ObservableBulkCreate,
    ObservableCreate,
    ObservableResponse,
    ObservableUpdate,
)
from src.services import observables as observable_service

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/observables",
    tags=["observables"],
)


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[ObservableResponse]])
async def list_observables(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.OBSERVABLE, Action.READ))
    ],
) -> ApiResponse[list[ObservableResponse]]:
    _check(auth, tenant_id)
    rows, total = await observable_service.list_observables(
        db, case_id, limit=pagination.page_size, offset=pagination.offset
    )
    # Compute cross-case counts for each
    responses = []
    for obs in rows:
        r = ObservableResponse.model_validate(obs)
        count = await observable_service.cross_case_count(
            db, tenant_id, obs.type, obs.value, obs.case_id
        )
        r = r.model_copy(update={"seen_in_cases_count": count})
        responses.append(r)
    return ApiResponse(
        data=responses,
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post(
    "",
    response_model=ApiResponse[ObservableResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_observable(
    tenant_id: UUID,
    case_id: UUID,
    payload: ObservableCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.OBSERVABLE, Action.CREATE))
    ],
) -> ApiResponse[ObservableResponse]:
    _check(auth, tenant_id)
    obs = await observable_service.create_observable(
        db, case_id=case_id, created_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=ObservableResponse.model_validate(obs))


@router.post(
    "/bulk",
    response_model=ApiResponse[list[ObservableResponse]],
    status_code=status.HTTP_201_CREATED,
)
async def create_observables_bulk(
    tenant_id: UUID,
    case_id: UUID,
    payload: ObservableBulkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.OBSERVABLE, Action.CREATE))
    ],
) -> ApiResponse[list[ObservableResponse]]:
    _check(auth, tenant_id)
    items = await observable_service.create_observables_bulk(
        db, case_id=case_id, created_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=[ObservableResponse.model_validate(o) for o in items])


@router.patch("/{observable_id}", response_model=ApiResponse[ObservableResponse])
async def update_observable(
    tenant_id: UUID,
    case_id: UUID,
    observable_id: UUID,
    payload: ObservableUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.OBSERVABLE, Action.UPDATE))
    ],
) -> ApiResponse[ObservableResponse]:
    _check(auth, tenant_id)
    obs = await observable_service.update_observable(db, observable_id, payload)
    return ApiResponse(data=ObservableResponse.model_validate(obs))


@router.delete("/{observable_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_observable(
    tenant_id: UUID,
    case_id: UUID,
    observable_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.OBSERVABLE, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await observable_service.delete_observable(db, observable_id)


__all__ = ["router"]

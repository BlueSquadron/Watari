"""Task endpoints (scoped under a case)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.tasks import TaskCreate, TaskResponse, TaskUpdate
from src.services import tasks as task_service

router = APIRouter(
    prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/tasks", tags=["tasks"]
)


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


@router.get("", response_model=ApiResponse[list[TaskResponse]])
async def list_tasks(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TASK, Action.READ))
    ],
) -> ApiResponse[list[TaskResponse]]:
    _check(auth, tenant_id)
    rows, total = await task_service.list_tasks(
        db, case_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[TaskResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post("", response_model=ApiResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_task(
    tenant_id: UUID,
    case_id: UUID,
    payload: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TASK, Action.CREATE))
    ],
) -> ApiResponse[TaskResponse]:
    _check(auth, tenant_id)
    task = await task_service.create_task(
        db, case_id=case_id, created_by=auth.user_id, payload=payload
    )
    return ApiResponse(data=TaskResponse.model_validate(task))


@router.patch("/{task_id}", response_model=ApiResponse[TaskResponse])
async def update_task(
    tenant_id: UUID,
    case_id: UUID,
    task_id: UUID,
    payload: TaskUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TASK, Action.UPDATE))
    ],
) -> ApiResponse[TaskResponse]:
    _check(auth, tenant_id)
    task = await task_service.update_task(db, task_id, payload, actor_id=auth.user_id)
    return ApiResponse(data=TaskResponse.model_validate(task))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    tenant_id: UUID,
    case_id: UUID,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[
        AuthContext, Depends(require_permission(Resource.TASK, Action.DELETE))
    ],
) -> None:
    _check(auth, tenant_id)
    await task_service.delete_task(db, task_id, actor_id=auth.user_id)


__all__ = ["router"]

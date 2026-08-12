"""Module management endpoints (platform-admin only)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import AuthContext, CurrentUserDep
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.modules import (
    ModuleExecutionResponse,
    ModuleRegister,
    ModuleResponse,
    ModuleUpdate,
)
from src.services import modules as module_service

router = APIRouter(prefix="/api/v1/admin/modules", tags=["modules"])


def _require_platform_admin(auth: CurrentUserDep) -> AuthContext:
    if not auth.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator role required")
    return auth


@router.get("", response_model=ApiResponse[list[ModuleResponse]])
async def list_modules(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin)],
) -> ApiResponse[list[ModuleResponse]]:
    rows, total = await module_service.list_modules(
        db, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[ModuleResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post("", response_model=ApiResponse[ModuleResponse], status_code=status.HTTP_201_CREATED)
async def register_module(
    payload: ModuleRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin)],
) -> ApiResponse[ModuleResponse]:
    module = await module_service.register_module(db, payload)
    return ApiResponse(data=ModuleResponse.model_validate(module))


@router.patch("/{module_id}", response_model=ApiResponse[ModuleResponse])
async def update_module(
    module_id: UUID,
    payload: ModuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin)],
) -> ApiResponse[ModuleResponse]:
    module = await module_service.update_module(db, module_id, payload)
    return ApiResponse(data=ModuleResponse.model_validate(module))


@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_module(
    module_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin)],
) -> None:
    await module_service.delete_module(db, module_id)


@router.get(
    "/{module_id}/executions",
    response_model=ApiResponse[list[ModuleExecutionResponse]],
)
async def list_executions(
    module_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _auth: Annotated[AuthContext, Depends(_require_platform_admin)],
) -> ApiResponse[list[ModuleExecutionResponse]]:
    rows, total = await module_service.list_executions(
        db, module_id=module_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[ModuleExecutionResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


__all__ = ["router"]

"""Notes endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Action, AuthContext, Resource, require_permission
from src.db import get_db
from src.schemas.common import ApiResponse, PaginationParams, build_pagination_meta
from src.schemas.notes import (
    NoteCreate,
    NoteFolderCreate,
    NoteFolderResponse,
    NoteFolderUpdate,
    NoteResponse,
    NoteUpdate,
)
from src.services import notes as notes_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/cases/{case_id}/notes", tags=["notes"])


def _check(auth: AuthContext, tenant_id: UUID) -> None:
    if not auth.is_platform_admin and auth.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant access denied")


# ---- Folders ----


@router.get("/folders", response_model=ApiResponse[list[NoteFolderResponse]])
async def list_folders(
    tenant_id: UUID,
    case_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.READ))],
) -> ApiResponse[list[NoteFolderResponse]]:
    _check(auth, tenant_id)
    folders = await notes_service.list_folders(db, case_id)
    return ApiResponse(data=[NoteFolderResponse.model_validate(f) for f in folders])


@router.post(
    "/folders",
    response_model=ApiResponse[NoteFolderResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_folder(
    tenant_id: UUID,
    case_id: UUID,
    payload: NoteFolderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.CREATE))],
) -> ApiResponse[NoteFolderResponse]:
    _check(auth, tenant_id)
    folder = await notes_service.create_folder(db, case_id, payload)
    return ApiResponse(data=NoteFolderResponse.model_validate(folder))


@router.patch("/folders/{folder_id}", response_model=ApiResponse[NoteFolderResponse])
async def update_folder(
    tenant_id: UUID,
    case_id: UUID,
    folder_id: UUID,
    payload: NoteFolderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.UPDATE))],
) -> ApiResponse[NoteFolderResponse]:
    _check(auth, tenant_id)
    folder = await notes_service.update_folder(db, folder_id, payload)
    return ApiResponse(data=NoteFolderResponse.model_validate(folder))


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    tenant_id: UUID,
    case_id: UUID,
    folder_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.DELETE))],
) -> None:
    _check(auth, tenant_id)
    await notes_service.delete_folder(db, folder_id)


# ---- Notes ----


@router.get("", response_model=ApiResponse[list[NoteResponse]])
async def list_notes(
    tenant_id: UUID,
    case_id: UUID,
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.READ))],
    folder_id: UUID | None = Query(default=None),
) -> ApiResponse[list[NoteResponse]]:
    _check(auth, tenant_id)
    rows, total = await notes_service.list_notes(
        db, case_id, folder_id=folder_id, limit=pagination.page_size, offset=pagination.offset
    )
    return ApiResponse(
        data=[NoteResponse.model_validate(r) for r in rows],
        meta=build_pagination_meta(total, pagination.page, pagination.page_size),
    )


@router.post("", response_model=ApiResponse[NoteResponse], status_code=status.HTTP_201_CREATED)
async def create_note(
    tenant_id: UUID,
    case_id: UUID,
    payload: NoteCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.CREATE))],
) -> ApiResponse[NoteResponse]:
    _check(auth, tenant_id)
    note = await notes_service.create_note(db, case_id, auth.user_id, payload)
    return ApiResponse(data=NoteResponse.model_validate(note))


@router.patch("/{note_id}", response_model=ApiResponse[NoteResponse])
async def update_note(
    tenant_id: UUID,
    case_id: UUID,
    note_id: UUID,
    payload: NoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.UPDATE))],
) -> ApiResponse[NoteResponse]:
    _check(auth, tenant_id)
    note = await notes_service.update_note(db, note_id, payload)
    return ApiResponse(data=NoteResponse.model_validate(note))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    tenant_id: UUID,
    case_id: UUID,
    note_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth: Annotated[AuthContext, Depends(require_permission(Resource.NOTE, Action.DELETE))],
) -> None:
    _check(auth, tenant_id)
    await notes_service.delete_note(db, note_id)


__all__ = ["router"]

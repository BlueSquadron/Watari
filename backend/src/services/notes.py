"""Note and folder service. Enforces a valid folder tree (no cycles)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Note, NoteFolder
from src.schemas.notes import (
    NoteCreate,
    NoteFolderCreate,
    NoteFolderUpdate,
    NoteUpdate,
)


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Case {case_id} not found")
    return case


async def _get_note_or_404(db: AsyncSession, note_id: UUID) -> Note:
    note = (await db.execute(select(Note).where(Note.id == note_id))).scalar_one_or_none()
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Note {note_id} not found")
    return note


async def _get_folder_or_404(db: AsyncSession, folder_id: UUID) -> NoteFolder:
    folder = (
        await db.execute(select(NoteFolder).where(NoteFolder.id == folder_id))
    ).scalar_one_or_none()
    if folder is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Folder {folder_id} not found")
    return folder


async def _would_create_cycle(
    db: AsyncSession, folder_id: UUID, new_parent_id: UUID
) -> bool:
    """True if moving folder_id under new_parent_id would create a cycle."""
    if folder_id == new_parent_id:
        return True
    current: UUID | None = new_parent_id
    visited: set[UUID] = set()
    while current is not None:
        if current == folder_id:
            return True
        if current in visited:
            return True
        visited.add(current)
        parent = (
            await db.execute(
                select(NoteFolder.parent_id).where(NoteFolder.id == current)
            )
        ).scalar_one_or_none()
        current = parent
    return False


# ---- Folders ----

async def list_folders(db: AsyncSession, case_id: UUID) -> list[NoteFolder]:
    return list(
        (
            await db.execute(
                select(NoteFolder)
                .where(NoteFolder.case_id == case_id)
                .order_by(NoteFolder.sort_order.asc(), NoteFolder.name.asc())
            )
        ).scalars().all()
    )


async def create_folder(
    db: AsyncSession, case_id: UUID, payload: NoteFolderCreate
) -> NoteFolder:
    case = await _get_case_or_404(db, case_id)
    if payload.parent_id is not None:
        parent = await _get_folder_or_404(db, payload.parent_id)
        if parent.case_id != case.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Parent folder belongs to a different case"
            )
    folder = NoteFolder(
        tenant_id=case.tenant_id,
        case_id=case.id,
        parent_id=payload.parent_id,
        name=payload.name,
        sort_order=payload.sort_order,
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    return folder


async def update_folder(
    db: AsyncSession, folder_id: UUID, payload: NoteFolderUpdate
) -> NoteFolder:
    folder = await _get_folder_or_404(db, folder_id)
    data = payload.model_dump(exclude_unset=True)
    if "parent_id" in data and data["parent_id"] is not None:
        if await _would_create_cycle(db, folder.id, data["parent_id"]):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Moving this folder would create a cycle in the folder tree",
            )
    for key, value in data.items():
        setattr(folder, key, value)
    await db.flush()
    await db.refresh(folder)
    return folder


async def delete_folder(db: AsyncSession, folder_id: UUID) -> None:
    folder = await _get_folder_or_404(db, folder_id)
    await db.delete(folder)
    await db.flush()


# ---- Notes ----

async def list_notes(
    db: AsyncSession,
    case_id: UUID,
    *,
    folder_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Note], int]:
    base = select(Note).where(Note.case_id == case_id)
    if folder_id is not None:
        base = base.where(Note.folder_id == folder_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(Note.updated_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)


async def create_note(
    db: AsyncSession, case_id: UUID, author_id: UUID, payload: NoteCreate
) -> Note:
    case = await _get_case_or_404(db, case_id)
    if payload.folder_id is not None:
        folder = await _get_folder_or_404(db, payload.folder_id)
        if folder.case_id != case.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Folder belongs to a different case")
    note = Note(
        tenant_id=case.tenant_id,
        case_id=case.id,
        folder_id=payload.folder_id,
        title=payload.title,
        content=payload.content,
        author_id=author_id,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return note


async def update_note(db: AsyncSession, note_id: UUID, payload: NoteUpdate) -> Note:
    note = await _get_note_or_404(db, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "folder_id" in data and data["folder_id"] is not None:
        folder = await _get_folder_or_404(db, data["folder_id"])
        if folder.case_id != note.case_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Folder belongs to a different case")
    for key, value in data.items():
        setattr(note, key, value)
    await db.flush()
    await db.refresh(note)
    return note


async def delete_note(db: AsyncSession, note_id: UUID) -> None:
    note = await _get_note_or_404(db, note_id)
    await db.delete(note)
    await db.flush()


__all__ = [
    "list_folders",
    "create_folder",
    "update_folder",
    "delete_folder",
    "list_notes",
    "create_note",
    "update_note",
    "delete_note",
]

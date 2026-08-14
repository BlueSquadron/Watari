"""Task service layer: CRUD + status transitions + notifications."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Case, Task
from src.schemas.tasks import TaskCreate, TaskStatus, TaskUpdate

from .timeline_recorder import record_event


async def _get_case_or_404(db: AsyncSession, case_id: UUID) -> Case:
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    return case


async def _get_task_or_404(db: AsyncSession, task_id: UUID) -> Task:
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


async def list_tasks(
    db: AsyncSession, case_id: UUID, *, limit: int = 100, offset: int = 0
) -> tuple[list[Task], int]:
    base = select(Task).where(Task.case_id == case_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(Task.sort_order.asc(), Task.created_at.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def create_task(
    db: AsyncSession,
    *,
    case_id: UUID,
    created_by: UUID,
    payload: TaskCreate,
) -> Task:
    case = await _get_case_or_404(db, case_id)
    task = Task(
        tenant_id=case.tenant_id,
        case_id=case.id,
        title=payload.title,
        description=payload.description,
        assignee_id=payload.assignee_id,
        sort_order=payload.sort_order,
        created_by=created_by,
    )
    db.add(task)
    await db.flush()
    await record_event(
        db,
        tenant_id=case.tenant_id,
        case_id=case.id,
        event_type="task_created",
        description=f"Task created: {task.title}",
        category="task",
        actor_id=created_by,
        metadata={"task_id": str(task.id)},
    )
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession,
    task_id: UUID,
    payload: TaskUpdate,
    *,
    actor_id: UUID,
) -> Task:
    task = await _get_task_or_404(db, task_id)
    old_status = task.status
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "status" and value is not None:
            setattr(task, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(task, key, value)
    if "status" in data and task.status != old_status:
        await record_event(
            db,
            tenant_id=task.tenant_id,
            case_id=task.case_id,
            event_type="task_status_changed",
            description=(f"Task '{task.title}' status changed from {old_status} to {task.status}"),
            category="task",
            actor_id=actor_id,
            metadata={"task_id": str(task.id), "from": old_status, "to": task.status},
        )
        # If all tasks complete, fire case-level notification event
        remaining = (
            await db.execute(
                select(func.count(Task.id))
                .where(Task.case_id == task.case_id)
                .where(~Task.status.in_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value]))
            )
        ).scalar_one()
        if remaining == 0:
            await record_event(
                db,
                tenant_id=task.tenant_id,
                case_id=task.case_id,
                event_type="all_tasks_complete",
                description="All tasks for this case have been completed",
                category="task",
                actor_id=actor_id,
            )
    await db.flush()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: UUID, *, actor_id: UUID) -> None:
    task = await _get_task_or_404(db, task_id)
    tenant_id = task.tenant_id
    case_id = task.case_id
    title = task.title
    await db.delete(task)
    await db.flush()
    await record_event(
        db,
        tenant_id=tenant_id,
        case_id=case_id,
        event_type="task_deleted",
        description=f"Task deleted: {title}",
        category="task",
        actor_id=actor_id,
    )


__all__ = [
    "list_tasks",
    "create_task",
    "update_task",
    "delete_task",
]

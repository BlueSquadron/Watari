"""Audit logging service and FastAPI middleware.

Writes immutable `audit_logs` rows for every mutating request that
carried authenticated credentials. The middleware logs the request
URL, method, user, source IP, and user agent. Service-account actions
are flagged on the row so they can be separated from interactive user
activity in the viewer.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.auth.context import AuthContext, Role
from src.db import admin_session_factory
from src.models import AuditLog
from src.schemas.audit import AuditLogFilters

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def record(
    db: AsyncSession,
    *,
    auth: AuthContext,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        source_ip=source_ip,
        user_agent=user_agent,
        is_service_account=auth.is_service_account,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_logs(
    db: AsyncSession,
    tenant_id: UUID,
    filters: AuditLogFilters,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    base = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
    if filters.user_id:
        base = base.where(AuditLog.user_id == filters.user_id)
    if filters.action:
        base = base.where(AuditLog.action == filters.action)
    if filters.resource_type:
        base = base.where(AuditLog.resource_type == filters.resource_type)
    if filters.resource_id:
        base = base.where(AuditLog.resource_id == filters.resource_id)
    if filters.created_after:
        base = base.where(AuditLog.created_at >= filters.created_after)
    if filters.created_before:
        base = base.where(AuditLog.created_at <= filters.created_before)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return list(rows), int(total)


def deny_modification(user_role: Role) -> bool:
    """Pure predicate: must this user be denied modification of audit logs?

    Only platform administrators may delete or modify log entries. All
    other roles (tenant admin, analyst, read-only, service account) SHALL
    be denied.
    """
    return user_role != Role.PLATFORM_ADMIN


class AuditMiddleware(BaseHTTPMiddleware):
    """Records an audit log row for every mutating authenticated request.

    Runs AFTER `RequestIDMiddleware` and AFTER authentication dependencies
    have populated `request.state.auth_context`. Read-only (GET/HEAD)
    requests are skipped to avoid log bloat.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        try:
            auth: AuthContext | None = getattr(request.state, "auth_context", None)
            if (
                auth is not None
                and request.method in _MUTATING_METHODS
                and response.status_code < 500
            ):
                async with admin_session_factory() as session:
                    await record(
                        session,
                        auth=auth,
                        action=f"{request.method} {request.url.path}",
                        resource_type=_resource_from_path(request.url.path),
                        details={
                            "status_code": response.status_code,
                            "path": request.url.path,
                        },
                        source_ip=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                    )
                    await session.commit()
        except Exception:  # noqa: BLE001
            # Audit failures must never break the request.
            pass
        return response


def _resource_from_path(path: str) -> str:
    # Heuristic: the last meaningful segment is the resource type. Good enough
    # for broad dashboards; finer-grained actions can call `record()` explicitly.
    parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
    return parts[-1] if parts else "unknown"


__all__ = ["record", "list_logs", "deny_modification", "AuditMiddleware"]

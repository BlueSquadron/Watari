"""Tenant-aware database session dependency.

Provides FastAPI dependencies that open an AsyncSession and configure
PostgreSQL session-local settings (`app.current_tenant` and
`app.is_platform_admin`) so that Row-Level Security policies enforce
tenant isolation transparently.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .engine import async_session_factory


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Authenticated tenant context extracted from the current request.

    Attributes:
        tenant_id: UUID of the tenant the user belongs to.
        is_platform_admin: True if the user has platform-wide admin privileges
            and should bypass tenant isolation (e.g., for cross-tenant support
            operations).
    """

    tenant_id: UUID
    is_platform_admin: bool = False


def get_tenant_context(request: Request) -> TenantContext | None:
    """Derive the `TenantContext` from the request's authenticated identity.

    The auth dependency (``src.auth.dependencies.get_current_user``)
    populates ``request.state.auth_context`` after validating the JWT or
    API key. This dependency reads that context and projects it onto the
    narrower `TenantContext` used by the DB session layer. Returns
    ``None`` for unauthenticated requests, causing `get_db` to open an
    unscoped session — suitable for public endpoints such as ``/health``
    and the auth/login routes.
    """
    auth_context = getattr(request.state, "auth_context", None)
    if auth_context is None:
        return None
    return TenantContext(
        tenant_id=auth_context.tenant_id,
        is_platform_admin=auth_context.is_platform_admin,
    )


async def get_db(
    tenant_context: TenantContext | None = Depends(get_tenant_context),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a tenant-scoped AsyncSession.

    When a `TenantContext` is present, issues `SET LOCAL` statements so
    that PostgreSQL RLS policies see the current tenant. Commits on
    successful completion of the request, rolls back on exception, and
    always closes the session.
    """
    async with async_session_factory() as session:
        try:
            if tenant_context is not None:
                # `SET LOCAL` does not accept bind parameters — PostgreSQL
                # rejects `SET LOCAL x = $1` as a syntax error. `set_config`
                # with is_local=true is the parameterizable equivalent.
                await session.execute(
                    text(
                        "SELECT set_config('app.current_tenant', :tenant_id, true)"
                    ).bindparams(tenant_id=str(tenant_context.tenant_id))
                )
                if tenant_context.is_platform_admin:
                    await session.execute(
                        text("SET LOCAL app.is_platform_admin = 'true'")
                    )
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def get_db_unscoped() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession without applying RLS tenant settings.

    For use by migrations, platform-admin-only tooling, and bootstrap
    tasks that must operate across all tenants. Callers are responsible
    for ensuring this is not exposed to untrusted requests.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()

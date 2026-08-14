"""Tenant-aware database session dependencies.

`get_db` opens a session on the RLS-enforcing connection. It carries no tenant
context of its own — the authentication dependency applies one via
`apply_tenant_context` as soon as it knows who the caller is, which is what
guarantees the context is in place before any endpoint body runs.

`get_db_unscoped` opens a session on the owner connection, which RLS does not
restrict. It is for work that is genuinely cross-tenant.
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .engine import admin_session_factory, async_session_factory


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


async def apply_tenant_context(session: AsyncSession, tenant_context: TenantContext) -> None:
    """Scope `session` to a tenant for the remainder of its transaction.

    Must be called before the session is used to read or write tenant data:
    the RLS policies read these settings, and a session without them matches
    no rows at all.

    `SET LOCAL` cannot take bind parameters — PostgreSQL rejects
    `SET LOCAL x = $1` as a syntax error — so the tenant id goes through
    `set_config(..., is_local => true)`, which is the parameterizable
    equivalent and is likewise scoped to the transaction.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)").bindparams(
            tenant_id=str(tenant_context.tenant_id)
        )
    )
    if tenant_context.is_platform_admin:
        await session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session on the RLS-enforcing connection, awaiting its tenant.

    The session starts with **no** tenant context, so the policies match
    nothing. The authentication dependency calls `apply_tenant_context` on this
    same session once it has resolved the user — FastAPI caches dependencies
    per request, so the endpoint receives the session already scoped.

    Ordering matters and used to be wrong. This dependency deliberately does
    *not* read `request.state.auth_context`: routers declare `db` before
    `auth`, so `get_db` is resolved first and that state does not exist yet.
    Letting the auth dependency push the context down is what makes the
    ordering a property of the dependency graph rather than of parameter
    order in 70 separate signatures.

    Commits on success, rolls back on exception, always closes.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def get_db_unscoped() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session on the owner connection, which RLS does not restrict.

    For work that is legitimately cross-tenant and therefore cannot be scoped:
    authentication lookups (there is no tenant to scope to until the user is
    resolved), tenant and user administration, and bootstrap tooling.

    This bypasses tenant isolation at the database level. Routes using it carry
    the whole burden of authorisation themselves — see the `_check(auth,
    tenant_id)` guards in `users.py` and `tenants.py`. Do not reach for it to
    make an ordinary tenant-scoped query work; if a query returns nothing on
    `get_db`, the tenant context is missing and that is the bug.
    """
    async with admin_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()

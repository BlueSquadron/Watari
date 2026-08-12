"""Shared FastAPI dependency aliases for route signatures."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import TenantContext, get_db, get_tenant_context

DBDep = Annotated[AsyncSession, Depends(get_db)]
"""Typed dependency for an RLS-scoped AsyncSession."""

TenantContextDep = Annotated[TenantContext | None, Depends(get_tenant_context)]
"""Typed dependency for the current tenant context (None for unauthenticated requests)."""

__all__ = ["DBDep", "TenantContextDep"]

"""Async SQLAlchemy engines and session factories.

Two engines, deliberately:

`engine` connects as the unprivileged application role and is therefore
*subject to* Row-Level Security. Everything on the request path uses it, and
every session it hands out is expected to carry a tenant context — without one
the policies match nothing and queries return no rows. That is the intended
failure mode: closed, not open.

`admin_engine` connects as the owner role and is not restricted by RLS. It is
for work that is legitimately cross-tenant and cannot have a tenant context:
authentication lookups (you cannot scope by tenant before you know who the user
is), tenant and user administration, the Celery worker, audit writes, and the
seed script.

If you reach for `admin_session_factory` on the request path, stop and check
whether the operation really is cross-tenant.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.utils import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

admin_engine: AsyncEngine = create_async_engine(
    settings.admin_database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

admin_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

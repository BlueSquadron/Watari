"""Shared pytest fixtures for backend tests.

Provides:
    - A session-scoped async engine pointed at a dedicated test database with
      the schema applied via Alembic migrations.
    - A per-test `db_session` fixture that wraps each test in a transaction
      which is rolled back on teardown, ensuring tests do not contaminate
      each other.
    - `tenant_factory` and `user_factory` helpers for quickly building test
      data scoped to the current `db_session`.

The tests that depend on these fixtures require a live PostgreSQL instance
because Row-Level Security policies and the `next_case_number` PL/pgSQL
function cannot be exercised against an in-memory substitute. Set
`TEST_DATABASE_URL` (or reuse `DATABASE_URL`) to point at a database that
the current role may create/drop tables in.

Two roles are involved, mirroring production:

    TEST_DATABASE_URL       the owner. Runs the migrations, which create the
                            schema and the application role itself.
    TEST_APP_DATABASE_URL   the unprivileged application role, which RLS
                            actually applies to. `db_session` uses this, so
                            tests run against the same enforcement the API
                            does. Derived from TEST_DATABASE_URL by default.

`db_session` opts into the platform-admin bypass, because most suites are
testing something other than isolation and would otherwise have to establish a
tenant context before every single insert. Tests that are about isolation turn
it off explicitly — see `tests/property/test_tenant_isolation.py`.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://watari:watari_dev_password@localhost:5432/watari_test",
)


def _default_app_url() -> str:
    """Swap the owner credentials for the application role's, same database."""
    from sqlalchemy.engine import make_url

    url = make_url(TEST_DATABASE_URL)
    return url.set(
        username=os.getenv("APP_DB_USER", "watari_app"),
        password=os.getenv("APP_DB_PASSWORD", "watari_app_dev_password"),
    ).render_as_string(hide_password=False)


TEST_APP_DATABASE_URL = os.getenv("TEST_APP_DATABASE_URL") or _default_app_url()


def _assert_disposable_database(url: str) -> None:
    """Refuse to migrate/drop anything that isn't obviously a test database.

    The session teardown runs `alembic downgrade base`, which drops every
    table. Running the suite against a development database would silently
    destroy it, so require the database name to say it is for tests.
    """
    from sqlalchemy.engine import make_url

    database = make_url(url).database or ""
    if "test" not in database.lower():
        pytest.exit(
            f"Refusing to run migrations against database {database!r}: the test "
            "suite drops every table on teardown. Point TEST_DATABASE_URL at a "
            "dedicated database whose name contains 'test' "
            "(e.g. postgresql+asyncpg://watari:...@localhost:5432/watari_test).",
            returncode=1,
        )


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create the async engine and apply schema once per test session.

    Teardown runs `downgrade base`, so this must never be pointed at a
    database anyone cares about — hence the guard below.
    """
    from alembic.config import Config

    from alembic import command

    _assert_disposable_database(TEST_DATABASE_URL)

    # The owner engine, for migrations and teardown only.
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # `alembic/env.py` drives migrations through an async engine of its own, so
    # the URL configured above is all it needs — no synchronous driver here.
    # It calls `asyncio.run()`, which cannot be nested inside this fixture's
    # running loop, so hand the migration to a worker thread that has none.
    await asyncio.to_thread(command.upgrade, config, "head")

    try:
        yield engine
    finally:
        await engine.dispose()
        await asyncio.to_thread(command.downgrade, config, "base")


@pytest_asyncio.fixture(scope="session")
async def app_engine(test_engine: AsyncEngine) -> AsyncGenerator[AsyncEngine, None]:
    """Engine for the unprivileged application role.

    Depends on `test_engine` so the migrations — which create this very role —
    have run first.
    """
    engine = create_async_engine(TEST_APP_DATABASE_URL, pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(app_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a per-test session wrapped in a rolled-back transaction.

    Each test gets its own session bound to a connection-level transaction
    which is rolled back on teardown, so database state never leaks between
    tests.

    Runs as the application role, so Row-Level Security applies exactly as it
    does in the API. The platform-admin bypass is switched on by default:
    without it every fixture that inserts a user or a case would first have to
    establish a tenant context, which is noise for the 27 suites that are not
    about isolation. Tests that *are* about isolation set
    `app.is_platform_admin` to 'false' themselves.
    """
    factory = async_sessionmaker(app_engine, expire_on_commit=False)
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        try:
            async with factory(bind=conn) as session:
                await session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))
                yield session
        finally:
            await tx.rollback()


TenantFactory = Callable[..., Awaitable["object"]]
UserFactory = Callable[..., Awaitable["object"]]


@pytest_asyncio.fixture
async def tenant_factory(db_session: AsyncSession) -> AsyncGenerator[TenantFactory, None]:
    """Factory producing test tenants attached to the current db_session."""
    from src.models import Tenant

    async def _create(name: str = "Test Tenant", slug_suffix: str = "") -> Tenant:
        slug = f"test-tenant-{uuid.uuid4().hex[:8]}{slug_suffix}"
        tenant = Tenant(name=name, slug=slug)
        db_session.add(tenant)
        await db_session.flush()
        return tenant

    yield _create


@pytest_asyncio.fixture
async def user_factory(db_session: AsyncSession) -> UserFactory:
    """Factory producing test users attached to the current db_session."""
    from src.models import User

    async def _create(
        tenant_id: uuid.UUID,
        username_suffix: str = "",
        role: str = "analyst",
    ) -> User:
        username = f"testuser-{uuid.uuid4().hex[:8]}{username_suffix}"
        user = User(
            tenant_id=tenant_id,
            username=username,
            email=f"{username}@test.local",
            display_name=f"Test {username}",
            role=role,
            password_hash="dummy",
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _create

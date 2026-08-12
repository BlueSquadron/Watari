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
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import pytest_asyncio
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


@pytest.fixture(scope="session")
def event_loop() -> "asyncio.AbstractEventLoop":
    """Provide a single event loop for all async tests in the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create the async engine and apply schema once per test session."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)

    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    # Alembic needs a synchronous driver URL.
    sync_url = TEST_DATABASE_URL.replace("+asyncpg", "")

    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.begin():
            command.upgrade(config, "head")
    finally:
        sync_engine.dispose()

    try:
        yield engine
    finally:
        sync_engine = create_engine(sync_url)
        try:
            with sync_engine.begin():
                command.downgrade(config, "base")
        finally:
            sync_engine.dispose()
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a per-test session wrapped in a rolled-back transaction.

    Each test gets its own session bound to a connection-level transaction
    which is rolled back on teardown, so database state never leaks between
    tests.
    """
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with test_engine.connect() as conn:
        tx = await conn.begin()
        try:
            async with factory(bind=conn) as session:
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

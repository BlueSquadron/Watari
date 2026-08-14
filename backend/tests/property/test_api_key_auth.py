"""Service-account API key authentication.

Watari documents `X-API-Key` as the credential an OCSF producer uses to ingest
alerts. There was no test for it at any level, which is how it came to be true
that no endpoint accepted one at all (#15).

These exercise the resolution step — plaintext key to `AuthContext` — against a
real database, because that is where the constraints live: the key is stored
only as a hash, and the lookup filters on `is_service_account` and `is_active`.

Requires a live PostgreSQL database.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import Role, generate_api_key, hash_api_key
from src.auth.api_keys import _load_service_account
from src.models import User

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE_URL") is None and os.getenv("DATABASE_URL") is None,
    reason="Requires PostgreSQL test database",
)


async def _make_service_account(
    db_session: AsyncSession, tenant_id, *, is_active: bool = True
) -> tuple[User, str]:
    """Create a service account and return it with its plaintext key."""
    key = generate_api_key()
    user = User(
        tenant_id=tenant_id,
        username=f"svc-{key[-8:]}",
        email=f"svc-{key[-8:]}@service.invalid",
        display_name="Automation",
        role=Role.API_SERVICE_ACCOUNT.value,
        password_hash="unused",
        is_service_account=True,
        is_active=is_active,
        api_key_hash=hash_api_key(key),
    )
    db_session.add(user)
    await db_session.flush()
    return user, key


@pytest.mark.asyncio
async def test_valid_key_resolves_to_its_own_tenant(
    db_session: AsyncSession, tenant_factory
) -> None:
    """The context carries the tenant, which is what scopes the request."""
    tenant = await tenant_factory()
    user, key = await _make_service_account(db_session, tenant.id)

    auth = await _load_service_account(key, db_session)

    assert auth.user_id == user.id
    assert auth.tenant_id == tenant.id
    assert auth.role == Role.API_SERVICE_ACCOUNT
    assert auth.is_service_account is True
    assert auth.is_platform_admin is False


@pytest.mark.asyncio
async def test_key_is_not_recoverable_from_the_database(
    db_session: AsyncSession, tenant_factory
) -> None:
    """Only the hash is persisted."""
    tenant = await tenant_factory()
    user, key = await _make_service_account(db_session, tenant.id)

    assert user.api_key_hash != key
    assert key not in (user.api_key_hash or "")


@pytest.mark.asyncio
async def test_wrong_key_is_rejected(db_session: AsyncSession, tenant_factory) -> None:
    tenant = await tenant_factory()
    await _make_service_account(db_session, tenant.id)

    with pytest.raises(HTTPException) as exc:
        await _load_service_account(generate_api_key(), db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_malformed_key_is_rejected(db_session: AsyncSession, tenant_factory) -> None:
    """Anything without the expected prefix is refused before any lookup."""
    tenant = await tenant_factory()
    await _make_service_account(db_session, tenant.id)

    for candidate in ("", "not-a-key", "Bearer something"):
        with pytest.raises(HTTPException) as exc:
            await _load_service_account(candidate, db_session)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_account_is_rejected(
    db_session: AsyncSession, tenant_factory
) -> None:
    """Disabling the account revokes the key immediately."""
    tenant = await tenant_factory()
    _user, key = await _make_service_account(db_session, tenant.id, is_active=False)

    with pytest.raises(HTTPException) as exc:
        await _load_service_account(key, db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_an_interactive_users_key_is_not_a_service_account_key(
    db_session: AsyncSession, tenant_factory, user_factory
) -> None:
    """The lookup filters on is_service_account, so a human's row cannot be
    used as a machine credential even if it somehow carries a key hash."""
    tenant = await tenant_factory()
    human = await user_factory(tenant.id, role="analyst")
    key = generate_api_key()
    human.api_key_hash = hash_api_key(key)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await _load_service_account(key, db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rotating_the_hash_invalidates_the_previous_key(
    db_session: AsyncSession, tenant_factory
) -> None:
    tenant = await tenant_factory()
    user, old_key = await _make_service_account(db_session, tenant.id)

    new_key = generate_api_key()
    user.api_key_hash = hash_api_key(new_key)
    await db_session.flush()

    assert (await _load_service_account(new_key, db_session)).user_id == user.id
    with pytest.raises(HTTPException) as exc:
        await _load_service_account(old_key, db_session)
    assert exc.value.status_code == 401

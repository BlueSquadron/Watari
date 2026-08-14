"""User service layer: CRUD, password changes, service account creation."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import (
    Role,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from src.models import Tenant, User
from src.schemas.users import (
    PasswordChange,
    ServiceAccountCreate,
    UserCreate,
    UserUpdate,
)


async def _get_tenant_or_404(db: AsyncSession, tenant_id: UUID) -> Tenant:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant {tenant_id} not found",
        )
    return tenant


async def list_users(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 25,
    offset: int = 0,
    include_service_accounts: bool = True,
) -> tuple[list[User], int]:
    """List users within a tenant with pagination."""
    query = select(User).where(User.tenant_id == tenant_id)
    if not include_service_accounts:
        query = query.where(User.is_service_account.is_(False))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (
        (await db.execute(query.order_by(User.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), int(total)


async def get_user(db: AsyncSession, user_id: UUID) -> User:
    """Fetch a user by id or raise 404."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return user


async def create_user(
    db: AsyncSession,
    tenant_id: UUID,
    payload: UserCreate,
) -> User:
    """Create a regular (non-service-account) user."""
    await _get_tenant_or_404(db, tenant_id)

    # Username must be unique per tenant
    existing = (
        await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == payload.username)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' already exists in this tenant",
        )

    if payload.role == Role.API_SERVICE_ACCOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /service-accounts to create API service accounts",
        )

    password_hash = hash_password(payload.password) if payload.password else None

    user = User(
        tenant_id=tenant_id,
        username=payload.username,
        email=payload.email,
        display_name=payload.display_name,
        role=payload.role.value,
        password_hash=password_hash,
        inactivity_timeout_minutes=payload.inactivity_timeout_minutes,
        is_service_account=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: UUID, payload: UserUpdate) -> User:
    """Apply a partial update to a user."""
    user = await get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    # Pull role enum into its string value
    if "role" in data and data["role"] is not None:
        data["role"] = data["role"].value if hasattr(data["role"], "value") else data["role"]
    for key, value in data.items():
        setattr(user, key, value)
    await db.flush()
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user_id: UUID, payload: PasswordChange) -> None:
    """Verify current password and replace with new password."""
    user = await get_user(db, user_id)
    if user.password_hash is None or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(payload.new_password)
    await db.flush()


async def deactivate_user(db: AsyncSession, user_id: UUID) -> User:
    """Set is_active=False. Also invalidates future auth but not active sessions.

    (Session invalidation is handled separately by session management.)
    """
    user = await get_user(db, user_id)
    user.is_active = False
    await db.flush()
    await db.refresh(user)
    return user


async def activate_user(db: AsyncSession, user_id: UUID) -> User:
    user = await get_user(db, user_id)
    user.is_active = True
    await db.flush()
    await db.refresh(user)
    return user


async def create_service_account(
    db: AsyncSession, tenant_id: UUID, payload: ServiceAccountCreate
) -> tuple[User, str]:
    """Create a new service account with a generated API key.

    Returns the user and the plaintext API key — the latter is shown
    exactly once to the caller.
    """
    await _get_tenant_or_404(db, tenant_id)

    if payload.role not in (Role.ANALYST, Role.READ_ONLY):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service account role must be 'analyst' or 'read_only'",
        )

    existing = (
        await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.username == payload.username)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' already exists in this tenant",
        )

    api_key = generate_api_key()
    user = User(
        tenant_id=tenant_id,
        username=payload.username,
        email=f"{payload.username}@service.invalid",
        display_name=payload.display_name,
        role=Role.API_SERVICE_ACCOUNT.value,
        is_service_account=True,
        api_key_hash=hash_api_key(api_key),
        permissions=payload.permissions,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user, api_key


async def rotate_api_key(db: AsyncSession, user_id: UUID) -> str:
    """Rotate the API key of a service account. Returns the new plaintext key."""
    user = await get_user(db, user_id)
    if not user.is_service_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only service accounts have API keys",
        )
    api_key = generate_api_key()
    user.api_key_hash = hash_api_key(api_key)
    await db.flush()
    return api_key


__all__ = [
    "list_users",
    "get_user",
    "create_user",
    "update_user",
    "change_password",
    "deactivate_user",
    "activate_user",
    "create_service_account",
    "rotate_api_key",
]

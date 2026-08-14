"""Property 2: RBAC Permission Enforcement.

For any user with a given role, and for any action on any resource, the
permission decision (allow/deny) SHALL be consistent with the role's
defined permission set. A user without the required permission SHALL
always be denied; a user with the permission SHALL always be allowed.

Feature: watari-case-management, Property 2: RBAC Permission Enforcement
**Validates: Requirements 2.3, 2.4, 2.7**

These tests do not touch the database — RBAC is a pure function over
the in-memory permission matrix, so they run in any environment.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.auth.context import AuthContext, Role
from src.auth.rbac import (
    PERMISSION_MATRIX,
    Action,
    Permission,
    Resource,
    has_permission,
)

# Build a fixed list of (role, resource, action) tuples for Hypothesis.
_ROLES = list(Role)
_RESOURCES = list(Resource)
_ACTIONS = list(Action)


def _make_context(role: Role, is_service_account: bool = False) -> AuthContext:
    return AuthContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="u",
        display_name="U",
        role=role,
        session_id="s",
        is_service_account=is_service_account,
    )


@given(
    role=st.sampled_from(_ROLES),
    resource=st.sampled_from(_RESOURCES),
    action=st.sampled_from(_ACTIONS),
)
def test_permission_decision_matches_matrix(role: Role, resource: Resource, action: Action) -> None:
    """has_permission(auth, resource, action) == (permission in matrix[role])."""
    auth = _make_context(role)
    decision = has_permission(auth, resource, action)

    if role == Role.PLATFORM_ADMIN:
        # Platform admin is explicitly granted everything.
        assert decision is True
        return

    expected = Permission(resource=resource, action=action) in PERMISSION_MATRIX.get(
        role, frozenset()
    )
    assert decision == expected


@given(role=st.sampled_from(_ROLES))
def test_role_has_self_consistent_permissions(role: Role) -> None:
    """For each role, every permission in its matrix entry is granted by has_permission."""
    auth = _make_context(role)
    for permission in PERMISSION_MATRIX.get(role, frozenset()):
        assert has_permission(auth, permission.resource, permission.action), (
            f"Role {role} should grant {permission} but does not"
        )


def test_platform_admin_is_allowed_everything() -> None:
    """Platform admin bypasses the matrix and passes every check."""
    auth = _make_context(Role.PLATFORM_ADMIN)
    for resource in Resource:
        for action in Action:
            assert has_permission(auth, resource, action), (
                f"Platform admin should be allowed {action} on {resource}"
            )


def test_read_only_cannot_write() -> None:
    """Read-only users can read but cannot create/update/delete anything."""
    auth = _make_context(Role.READ_ONLY)
    write_actions = (Action.CREATE, Action.UPDATE, Action.DELETE)
    for resource in Resource:
        for action in write_actions:
            assert not has_permission(auth, resource, action), (
                f"Read-only should not be allowed {action} on {resource}"
            )


def test_analyst_cannot_manage_users() -> None:
    """Analysts do not have user-management privileges."""
    auth = _make_context(Role.ANALYST)
    for action in (Action.CREATE, Action.UPDATE, Action.DELETE):
        assert not has_permission(auth, Resource.USER, action)


def test_tenant_admin_can_manage_users() -> None:
    """Tenant admins have full CRUD on users within their tenant."""
    auth = _make_context(Role.TENANT_ADMIN)
    for action in (Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE):
        assert has_permission(auth, Resource.USER, action)


@pytest.mark.parametrize(
    "resource,action",
    [
        (Resource.CASE, Action.READ),
        (Resource.OBSERVABLE, Action.READ),
        (Resource.DASHBOARD, Action.READ),
    ],
)
def test_every_role_can_read_basic_resources(resource: Resource, action: Action) -> None:
    """All non-service-account roles can at least read basic case data."""
    for role in (Role.READ_ONLY, Role.ANALYST, Role.TENANT_ADMIN, Role.PLATFORM_ADMIN):
        auth = _make_context(role)
        assert has_permission(auth, resource, action), (
            f"Role {role} should be able to {action} on {resource}"
        )


# --- Service accounts (#15) ------------------------------------------------


def test_service_account_can_work_alerts_and_cases() -> None:
    """An API key is for automation: ingest findings, then work the case.

    This is the permission set behind the OCSF ingestion path documented in
    the README. It was an empty frozenset, so every service-account request
    was denied even once the key authenticated.
    """
    auth = _make_context(Role.API_SERVICE_ACCOUNT, is_service_account=True)
    for action in (Action.CREATE, Action.READ, Action.UPDATE):
        assert has_permission(auth, Resource.ALERT, action)
    for resource in (Resource.CASE, Resource.OBSERVABLE, Resource.TIMELINE):
        assert has_permission(auth, resource, Action.CREATE)
        assert has_permission(auth, resource, Action.READ)


def test_service_account_is_not_an_admin() -> None:
    """A leaked key must not be able to manage the tenant or its users."""
    auth = _make_context(Role.API_SERVICE_ACCOUNT, is_service_account=True)
    for action in (Action.CREATE, Action.UPDATE, Action.DELETE):
        assert not has_permission(auth, Resource.USER, action)
        assert not has_permission(auth, Resource.TENANT, action)
    assert not has_permission(auth, Resource.AUDIT_LOG, Action.READ)


def test_service_account_matches_analyst_exactly() -> None:
    """Service accounts are granted the analyst set — no more, no less.

    Pinned deliberately: widening this is a security decision, and it should
    fail here rather than be noticed in production.
    """
    assert PERMISSION_MATRIX[Role.API_SERVICE_ACCOUNT] == PERMISSION_MATRIX[Role.ANALYST]

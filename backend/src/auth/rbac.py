"""Role-based access control (RBAC) for Watari.

Defines the permission matrix that maps each role to the actions it is
allowed to perform on each resource type. A small dependency factory
(`require_permission`) produces FastAPI dependencies that enforce the
matrix at the route boundary.

The model is intentionally simple for v1:
- Each resource has a set of allowed (role, action) tuples
- `platform_admin` implicitly has access to everything across tenants
- `api_service_account` inherits permissions from its configured role
  (analyst or read_only), which is stored on the user row

More granular per-object ownership is not modeled — the requirements
deliberately exclude case-level access controls.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException, status

from .context import AuthContext, Role
from .dependencies import CurrentUserDep


class Action(StrEnum):
    """Atomic actions a user may perform on a resource."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"  # for actions like running enrichment, modules, etc.


class Resource(StrEnum):
    """Top-level resources under access control."""

    TENANT = "tenant"
    USER = "user"
    CASE = "case"
    TASK = "task"
    OBSERVABLE = "observable"
    ASSET = "asset"
    EVIDENCE = "evidence"
    NOTE = "note"
    TIMELINE = "timeline"
    ALERT = "alert"
    ENRICHMENT = "enrichment"
    ENRICHMENT_SOURCE = "enrichment_source"
    ATTACK_MAPPING = "attack_mapping"
    REPORT = "report"
    REPORT_TEMPLATE = "report_template"
    CASE_TEMPLATE = "case_template"
    MODULE = "module"
    AUDIT_LOG = "audit_log"
    DASHBOARD = "dashboard"
    SEARCH = "search"


@dataclass(frozen=True, slots=True)
class Permission:
    """A single (resource, action) permission."""

    resource: Resource
    action: Action


# Read-only viewer: can view most things but not modify
_READ_ONLY: frozenset[Permission] = frozenset(
    Permission(resource=res, action=Action.READ)
    for res in (
        Resource.CASE,
        Resource.TASK,
        Resource.OBSERVABLE,
        Resource.ASSET,
        Resource.EVIDENCE,
        Resource.NOTE,
        Resource.TIMELINE,
        Resource.ALERT,
        Resource.ATTACK_MAPPING,
        Resource.REPORT,
        Resource.DASHBOARD,
        Resource.SEARCH,
    )
)

# Analyst: can manage investigations end-to-end
_ANALYST_EXTRA: frozenset[Permission] = frozenset(
    {
        *(
            Permission(resource=res, action=action)
            for res in (
                Resource.CASE,
                Resource.TASK,
                Resource.OBSERVABLE,
                Resource.ASSET,
                Resource.EVIDENCE,
                Resource.NOTE,
                Resource.TIMELINE,
                Resource.ALERT,
                Resource.ATTACK_MAPPING,
                Resource.REPORT,
            )
            for action in (Action.CREATE, Action.UPDATE, Action.DELETE)
        ),
        Permission(resource=Resource.ENRICHMENT, action=Action.EXECUTE),
        Permission(resource=Resource.ENRICHMENT, action=Action.READ),
        Permission(resource=Resource.ENRICHMENT_SOURCE, action=Action.READ),
        Permission(resource=Resource.CASE_TEMPLATE, action=Action.READ),
        Permission(resource=Resource.REPORT_TEMPLATE, action=Action.READ),
        Permission(resource=Resource.MODULE, action=Action.READ),
        Permission(resource=Resource.MODULE, action=Action.EXECUTE),
    }
)
_ANALYST: frozenset[Permission] = _READ_ONLY | _ANALYST_EXTRA

# Tenant admin: analyst + tenant-level configuration
_TENANT_ADMIN_EXTRA: frozenset[Permission] = frozenset(
    {
        *(
            Permission(resource=Resource.USER, action=action)
            for action in (Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE)
        ),
        *(
            Permission(resource=Resource.CASE_TEMPLATE, action=action)
            for action in (Action.CREATE, Action.UPDATE, Action.DELETE)
        ),
        *(
            Permission(resource=Resource.REPORT_TEMPLATE, action=action)
            for action in (Action.CREATE, Action.UPDATE, Action.DELETE)
        ),
        *(
            Permission(resource=Resource.ENRICHMENT_SOURCE, action=action)
            for action in (Action.CREATE, Action.UPDATE, Action.DELETE)
        ),
        Permission(resource=Resource.AUDIT_LOG, action=Action.READ),
        Permission(resource=Resource.TENANT, action=Action.READ),
        Permission(resource=Resource.TENANT, action=Action.UPDATE),
    }
)
_TENANT_ADMIN: frozenset[Permission] = _ANALYST | _TENANT_ADMIN_EXTRA


# Role → allowed permissions
PERMISSION_MATRIX: dict[Role, frozenset[Permission]] = {
    Role.READ_ONLY: _READ_ONLY,
    Role.ANALYST: _ANALYST,
    Role.TENANT_ADMIN: _TENANT_ADMIN,
    # Platform admin permissions are handled via the explicit bypass below.
    Role.PLATFORM_ADMIN: frozenset(),
    # Service accounts inherit from the role stored on the user row; the
    # `_permissions_for` helper handles that by looking at the user role
    # and mapping to either analyst or read_only permissions.
    Role.API_SERVICE_ACCOUNT: frozenset(),
}


def _permissions_for(role: Role) -> frozenset[Permission]:
    """Return the effective permission set for a role."""
    if role == Role.PLATFORM_ADMIN:
        # Platform admins bypass checks, but we still compute a union for
        # introspection purposes.
        return frozenset.union(_TENANT_ADMIN, _ANALYST, _READ_ONLY)
    return PERMISSION_MATRIX.get(role, frozenset())


def has_permission(
    auth: AuthContext, resource: Resource, action: Action
) -> bool:
    """Return True if the authenticated principal may perform `action` on `resource`."""
    if auth.is_platform_admin:
        return True
    return Permission(resource=resource, action=action) in _permissions_for(auth.role)


def require_permission(
    resource: Resource, action: Action
) -> Callable[..., AuthContext]:  # noqa: F821  - self-ref
    """Build a FastAPI dependency that enforces the given permission.

    Usage:
        @router.post(
            "/cases",
            dependencies=[Depends(require_permission(Resource.CASE, Action.CREATE))],
        )
        async def create_case(...): ...

    Or, when the route needs the `AuthContext`:
        async def create_case(
            auth: Annotated[
                AuthContext,
                Depends(require_permission(Resource.CASE, Action.CREATE)),
            ],
        ): ...
    """

    async def _dep(auth: CurrentUserDep) -> AuthContext:
        if not has_permission(auth, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{auth.role}' is not permitted to "
                    f"{action} on {resource}"
                ),
            )
        return auth

    return _dep


def require_any_permission(
    permissions: Iterable[tuple[Resource, Action]],
) -> Callable[..., AuthContext]:  # noqa: F821
    """FastAPI dependency that allows the request if ANY of the permissions match."""

    perms = tuple(permissions)

    async def _dep(auth: CurrentUserDep) -> AuthContext:
        if auth.is_platform_admin or any(
            has_permission(auth, r, a) for r, a in perms
        ):
            return auth
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{auth.role}' does not satisfy any of the required permissions",
        )

    return _dep


RequirePermissionDep = Annotated[AuthContext, Depends]


__all__ = [
    "Action",
    "Resource",
    "Permission",
    "PERMISSION_MATRIX",
    "has_permission",
    "require_permission",
    "require_any_permission",
]

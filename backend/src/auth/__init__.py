"""Authentication and authorization primitives for the Watari API."""

from .api_keys import (
    OptionalServiceAccountDep,
    ServiceAccountDep,
    generate_api_key,
    get_service_account,
    get_service_account_optional,
    hash_api_key,
    verify_api_key,
)
from .context import AuthContext, Role
from .dependencies import (
    OAUTH2_SCHEME,
    CurrentUserDep,
    OptionalCurrentUserDep,
    get_current_user,
    get_current_user_optional,
)
from .jwt import TokenPayload, create_access_token, create_refresh_token, decode_token
from .passwords import hash_password, verify_password
from .rbac import (
    PERMISSION_MATRIX,
    Action,
    Permission,
    Resource,
    has_permission,
    require_any_permission,
    require_permission,
)
from .unified import PrincipalDep, get_principal

__all__ = [
    "AuthContext",
    "Role",
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
    "OAUTH2_SCHEME",
    "CurrentUserDep",
    "OptionalCurrentUserDep",
    "get_current_user",
    "get_current_user_optional",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    "ServiceAccountDep",
    "OptionalServiceAccountDep",
    "get_service_account",
    "get_service_account_optional",
    "PrincipalDep",
    "get_principal",
    "Action",
    "Resource",
    "Permission",
    "PERMISSION_MATRIX",
    "has_permission",
    "require_permission",
    "require_any_permission",
]

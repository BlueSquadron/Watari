"""OIDC authentication flow using Authlib.

Provides a pluggable OIDC provider configuration with the standard
authorization-code flow:

1. `GET /auth/oidc/{provider}/login` redirects to the IdP
2. IdP redirects back to `/auth/oidc/{provider}/callback?code=...&state=...`
3. The callback exchanges the code for tokens and returns a Watari JWT

Provider configuration is stored in environment variables:
- OIDC_{PROVIDER}_CLIENT_ID
- OIDC_{PROVIDER}_CLIENT_SECRET
- OIDC_{PROVIDER}_DISCOVERY_URL  (the .well-known/openid-configuration URL)
- OIDC_{PROVIDER}_SCOPES         (space-separated, default "openid email profile")

For v1 we support a single "default" provider. Multi-provider support
can be added by making `get_oauth_client` dispatch on the provider name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from authlib.integrations.starlette_client import OAuth

_oauth: OAuth | None = None


@dataclass(frozen=True, slots=True)
class OIDCClaims:
    """Claims extracted from an OIDC userinfo response."""

    subject: str  # unique stable ID from the IdP
    email: str
    name: str
    preferred_username: str | None = None
    groups: tuple[str, ...] = ()


def is_oidc_configured() -> bool:
    """Return True if OIDC env vars are set for the default provider."""
    return bool(
        os.getenv("OIDC_DEFAULT_CLIENT_ID")
        and os.getenv("OIDC_DEFAULT_CLIENT_SECRET")
        and os.getenv("OIDC_DEFAULT_DISCOVERY_URL")
    )


def get_oauth_client() -> OAuth:
    """Return the configured Authlib OAuth registry (lazy-initialized)."""
    global _oauth
    if _oauth is not None:
        return _oauth
    oauth = OAuth()
    if is_oidc_configured():
        oauth.register(
            name="default",
            server_metadata_url=os.environ["OIDC_DEFAULT_DISCOVERY_URL"],
            client_id=os.environ["OIDC_DEFAULT_CLIENT_ID"],
            client_secret=os.environ["OIDC_DEFAULT_CLIENT_SECRET"],
            client_kwargs={
                "scope": os.getenv(
                    "OIDC_DEFAULT_SCOPES", "openid email profile"
                )
            },
        )
    _oauth = oauth
    return oauth


def claims_from_userinfo(userinfo: dict[str, object]) -> OIDCClaims:
    """Extract a stable `OIDCClaims` tuple from a provider's userinfo payload."""
    groups_raw = userinfo.get("groups") or userinfo.get("roles") or ()
    if isinstance(groups_raw, str):
        groups: tuple[str, ...] = (groups_raw,)
    elif isinstance(groups_raw, (list, tuple)):
        groups = tuple(str(g) for g in groups_raw)
    else:
        groups = ()

    return OIDCClaims(
        subject=str(userinfo["sub"]),
        email=str(userinfo.get("email", "")),
        name=str(userinfo.get("name", userinfo.get("email", ""))),
        preferred_username=(
            str(userinfo["preferred_username"])
            if "preferred_username" in userinfo
            else None
        ),
        groups=groups,
    )


__all__ = [
    "OIDCClaims",
    "claims_from_userinfo",
    "get_oauth_client",
    "is_oidc_configured",
]

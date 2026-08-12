"""SAML SSO authentication flow.

v1 ships with a thin SAML facade that parses SAML assertions and maps
them onto the same `ExternalClaims` shape used by OIDC. We use the
`python3-saml` library when available; otherwise this module raises
`NotImplementedError` so the feature degrades gracefully.

SAML integration is deployment-specific (certificates, metadata, ACS
URLs), so the actual IdP configuration is expected to live in env vars:

- SAML_IDP_METADATA_URL
- SAML_SP_ENTITY_ID
- SAML_SP_ACS_URL
- SAML_SP_X509_CERT
- SAML_SP_PRIVATE_KEY

The endpoints wiring (GET /auth/saml/login, POST /auth/saml/acs) live
in the auth router (built in a later task); this module provides the
assertion-parsing helpers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SAMLAttributes:
    """Attributes extracted from a verified SAML assertion."""

    name_id: str
    email: str
    display_name: str
    groups: tuple[str, ...] = ()


def is_saml_configured() -> bool:
    """Return True if the required SAML environment variables are set."""
    required = (
        "SAML_IDP_METADATA_URL",
        "SAML_SP_ENTITY_ID",
        "SAML_SP_ACS_URL",
    )
    return all(os.getenv(var) for var in required)


def parse_saml_response(saml_response_b64: str) -> SAMLAttributes:
    """Parse and validate a SAML response, returning the extracted attributes.

    This is a minimal stub. Production deployments should use
    `onelogin.saml2` (from python3-saml) to validate signatures,
    conditions, and audience restrictions. We raise NotImplementedError
    until the library is wired in, so the feature is clearly flagged as
    deployment-specific.
    """
    raise NotImplementedError(
        "SAML response parsing requires the python3-saml library and "
        "deployment-specific IdP metadata. Configure the SAML_* environment "
        "variables and install the optional `saml` extra to enable SSO."
    )


__all__ = [
    "SAMLAttributes",
    "is_saml_configured",
    "parse_saml_response",
]

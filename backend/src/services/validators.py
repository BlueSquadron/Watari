"""Observable format validators.

Each validator takes a string value and returns a normalized form if
valid, or raises ``ValueError`` if the value does not match the format
specification for its observable type.

Supports: ip (v4 + v6), domain, hostname, url, hash_md5, hash_sha1,
hash_sha256, email, filename, registry_key.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from src.schemas.observables import ObservableType

# Pre-compiled patterns
_DOMAIN_LABEL = r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
_DOMAIN_RE = re.compile(rf"^(?:{_DOMAIN_LABEL}\.)+[A-Za-z]{{2,63}}$")
_HOSTNAME_RE = re.compile(rf"^(?:{_DOMAIN_LABEL})(?:\.{_DOMAIN_LABEL})*$")
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
_MD5_RE = re.compile(r"^[a-fA-F0-9]{32}$")
_SHA1_RE = re.compile(r"^[a-fA-F0-9]{40}$")
_SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
_REGISTRY_KEY_RE = re.compile(r"^HK(?:LM|CU|CR|U|CC)\\[^\x00]+$", re.IGNORECASE)
_FILENAME_RE = re.compile(r"^[^\x00/\r\n\t]+$")


def _normalize_domain(value: str) -> str:
    v = value.strip().lower().rstrip(".")
    if not _DOMAIN_RE.match(v):
        raise ValueError("not a valid domain name")
    return v


def _normalize_hostname(value: str) -> str:
    v = value.strip().lower().rstrip(".")
    if not v or not _HOSTNAME_RE.match(v):
        raise ValueError("not a valid hostname")
    return v


def _normalize_ip(value: str) -> str:
    v = value.strip()
    # Will raise ValueError on invalid IPs (IPv4 or IPv6)
    ip = ipaddress.ip_address(v)
    return str(ip)


def _normalize_url(value: str) -> str:
    v = value.strip()
    if len(v) > 4096:
        raise ValueError("URL too long")
    parsed = urlparse(v)
    if parsed.scheme not in {"http", "https", "ftp", "ftps"}:
        raise ValueError("URL must use http, https, ftp, or ftps scheme")
    if not parsed.netloc:
        raise ValueError("URL is missing a network location")
    return v


def _normalize_email(value: str) -> str:
    v = value.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("not a valid email address")
    return v


def _normalize_hash(value: str, pattern: re.Pattern[str], label: str) -> str:
    v = value.strip().lower()
    if not pattern.match(v):
        raise ValueError(f"not a valid {label} hash")
    return v


def _normalize_filename(value: str) -> str:
    v = value.strip()
    if not v or not _FILENAME_RE.match(v) or len(v) > 500:
        raise ValueError("not a valid filename")
    return v


def _normalize_registry_key(value: str) -> str:
    v = value.strip()
    if not _REGISTRY_KEY_RE.match(v):
        raise ValueError("not a valid Windows registry key (must start with HKLM\\, HKCU\\, etc.)")
    return v


_NORMALIZERS = {
    ObservableType.IP: _normalize_ip,
    ObservableType.DOMAIN: _normalize_domain,
    ObservableType.HOSTNAME: _normalize_hostname,
    ObservableType.URL: _normalize_url,
    ObservableType.HASH_MD5: lambda v: _normalize_hash(v, _MD5_RE, "MD5"),
    ObservableType.HASH_SHA1: lambda v: _normalize_hash(v, _SHA1_RE, "SHA1"),
    ObservableType.HASH_SHA256: lambda v: _normalize_hash(v, _SHA256_RE, "SHA256"),
    ObservableType.EMAIL: _normalize_email,
    ObservableType.FILENAME: _normalize_filename,
    ObservableType.REGISTRY_KEY: _normalize_registry_key,
}


def validate_observable(type: ObservableType, value: str) -> str:
    """Validate and normalize an observable value for its declared type.

    Raises ``ValueError`` with a descriptive message when the value does not
    conform to the type's format.
    """
    normalizer = _NORMALIZERS[type]
    return normalizer(value)


__all__ = ["validate_observable"]

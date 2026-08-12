"""Property 6: Observable Format Validation.

For any observable value and declared type, the validation function SHALL
accept values conforming to the type's format specification and SHALL
reject values that do not conform.

Feature: watari-case-management, Property 6: Observable Format Validation
**Validates: Requirements 6.3, 6.6**

Pure function tests — no database required.
"""

from __future__ import annotations

import hashlib
import ipaddress
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.schemas.observables import ObservableType
from src.services.validators import validate_observable

# ---------------------------------------------------------------------------
# Positive cases: valid inputs must be accepted and normalized
# ---------------------------------------------------------------------------


@given(
    octets=st.lists(
        st.integers(min_value=0, max_value=255), min_size=4, max_size=4
    )
)
@settings(max_examples=100)
def test_valid_ipv4_accepted(octets: list[int]) -> None:
    value = ".".join(str(o) for o in octets)
    assert validate_observable(ObservableType.IP, value) == value


@given(
    hex_groups=st.lists(
        st.text(alphabet="0123456789abcdef", min_size=1, max_size=4),
        min_size=8,
        max_size=8,
    )
)
@settings(max_examples=50)
def test_valid_ipv6_accepted(hex_groups: list[str]) -> None:
    value = ":".join(hex_groups)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        # Hypothesis occasionally generates ambiguous forms; skip
        pytest.skip("generator produced non-valid IPv6")
    normalized = validate_observable(ObservableType.IP, value)
    assert ipaddress.ip_address(normalized) == ipaddress.ip_address(value)


@given(
    content=st.binary(min_size=1, max_size=1024),
)
@settings(max_examples=50)
def test_valid_md5_accepted(content: bytes) -> None:
    h = hashlib.md5(content).hexdigest()
    assert validate_observable(ObservableType.HASH_MD5, h) == h
    # Mixed-case hex also accepted and normalized lower
    assert validate_observable(ObservableType.HASH_MD5, h.upper()) == h


@given(
    content=st.binary(min_size=1, max_size=1024),
)
@settings(max_examples=50)
def test_valid_sha1_accepted(content: bytes) -> None:
    h = hashlib.sha1(content).hexdigest()
    assert validate_observable(ObservableType.HASH_SHA1, h) == h


@given(
    content=st.binary(min_size=1, max_size=1024),
)
@settings(max_examples=50)
def test_valid_sha256_accepted(content: bytes) -> None:
    h = hashlib.sha256(content).hexdigest()
    assert validate_observable(ObservableType.HASH_SHA256, h) == h


@given(
    local=st.text(
        alphabet=string.ascii_lowercase + string.digits + "._-", min_size=1, max_size=30
    ).filter(lambda s: s and s[0] != "." and s[-1] != "."),
    domain_labels=st.lists(
        st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=20),
        min_size=2,
        max_size=3,
    ),
    tld=st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=6),
)
@settings(max_examples=100)
def test_valid_email_accepted(local: str, domain_labels: list[str], tld: str) -> None:
    email = f"{local}@{'.'.join(domain_labels)}.{tld}"
    assert validate_observable(ObservableType.EMAIL, email) == email.lower()


# ---------------------------------------------------------------------------
# Negative cases: invalid inputs must be rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["not-an-ip", "999.999.999.999", "256.0.0.1", "1.2.3", "abcd", ""],
)
def test_invalid_ip_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.IP, value)


@pytest.mark.parametrize(
    "value",
    ["xyzz" * 8, "g" * 32, "a" * 31, "a" * 33, "", "   "],
)
def test_invalid_md5_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.HASH_MD5, value)


@pytest.mark.parametrize(
    "value",
    ["a" * 39, "a" * 41, "xyz" + "a" * 37, "", "g" * 40],
)
def test_invalid_sha1_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.HASH_SHA1, value)


@pytest.mark.parametrize(
    "value",
    ["a" * 63, "a" * 65, "xyz" + "a" * 61, "", "g" * 64],
)
def test_invalid_sha256_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.HASH_SHA256, value)


@pytest.mark.parametrize(
    "value",
    ["not-an-email", "a@b", "@example.com", "foo@", "", "a b@example.com"],
)
def test_invalid_email_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.EMAIL, value)


@pytest.mark.parametrize(
    "value",
    ["not-a-url", "ftp://", "://foo", "http://", "javascript:alert(1)", ""],
)
def test_invalid_url_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.URL, value)


@pytest.mark.parametrize("value", ["not-a-registry-key", "HKLM", "", "C:\\Windows"])
def test_invalid_registry_key_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_observable(ObservableType.REGISTRY_KEY, value)


# ---------------------------------------------------------------------------
# Idempotence: normalizing a normalized value returns the same value
# ---------------------------------------------------------------------------


@given(
    content=st.binary(min_size=1, max_size=256),
)
@settings(max_examples=30)
def test_hash_normalization_is_idempotent(content: bytes) -> None:
    h = hashlib.sha256(content).hexdigest().upper()
    once = validate_observable(ObservableType.HASH_SHA256, h)
    twice = validate_observable(ObservableType.HASH_SHA256, once)
    assert once == twice

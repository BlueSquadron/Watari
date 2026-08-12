"""Property 22: Encrypted Evidence Round-Trip.

For any evidence file uploaded with password protection, encrypting the
file with the password and then decrypting with the same password SHALL
produce content identical to the original file.

Feature: watari-case-management, Property 22: Encrypted Evidence Round-Trip
**Validates: Requirements 17.7**
"""

from __future__ import annotations

import pytest
from cryptography.exceptions import InvalidTag
from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.storage import decrypt_with_password, encrypt_with_password


@given(
    plaintext=st.binary(min_size=0, max_size=4096),
    password=st.text(min_size=1, max_size=128),
)
@settings(max_examples=30, deadline=None)
def test_encrypt_decrypt_round_trip(plaintext: bytes, password: str) -> None:
    """decrypt(encrypt(x, pw), pw) == x for any x and any password."""
    ct = encrypt_with_password(plaintext, password)
    pt = decrypt_with_password(ct, password)
    assert pt == plaintext


@given(
    plaintext=st.binary(min_size=1, max_size=1024),
    good=st.text(min_size=1, max_size=32),
    bad=st.text(min_size=1, max_size=32),
)
@settings(max_examples=15, deadline=None)
def test_wrong_password_fails(plaintext: bytes, good: str, bad: str) -> None:
    """Decryption with a wrong password SHALL raise InvalidTag."""
    if good == bad:
        return  # skip accidentally-equal cases
    ct = encrypt_with_password(plaintext, good)
    with pytest.raises(InvalidTag):
        decrypt_with_password(ct, bad)


@given(
    plaintext=st.binary(min_size=1, max_size=1024),
    password=st.text(min_size=1, max_size=32),
)
@settings(max_examples=10, deadline=None)
def test_ciphertext_differs_from_plaintext(plaintext: bytes, password: str) -> None:
    """Ciphertext SHALL be distinct from plaintext and include a salt+nonce prefix."""
    ct = encrypt_with_password(plaintext, password)
    assert ct != plaintext
    # salt(16) + nonce(12) + >=16 bytes of tag
    assert len(ct) >= 16 + 12 + 16

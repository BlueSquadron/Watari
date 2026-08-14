"""Property 21: Evidence Hash Verification.

For any uploaded evidence file, the system SHALL compute the SHA256 hash
of the file content and compare it to the declared hash. The integrity
check SHALL report a match when hashes are equal and a mismatch when
they differ.

Feature: watari-case-management, Property 21: Evidence Hash Verification
**Validates: Requirements 17.5, 17.9**
"""

from __future__ import annotations

import hashlib

from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.storage import compute_sha256


@given(
    content=st.binary(min_size=0, max_size=4096),
)
@settings(max_examples=200)
def test_compute_sha256_matches_hashlib(content: bytes) -> None:
    """compute_sha256 SHALL match hashlib.sha256 for any bytes input."""
    assert compute_sha256(content) == hashlib.sha256(content).hexdigest()


@given(
    content=st.binary(min_size=1, max_size=4096),
    flip_index=st.integers(min_value=0, max_value=4095),
)
@settings(max_examples=100)
def test_hash_mismatch_detected_when_content_modified(content: bytes, flip_index: int) -> None:
    """Changing a single byte SHALL produce a different hash."""
    declared = hashlib.sha256(content).hexdigest()
    if flip_index >= len(content):
        return  # index out of range for short content, not a counterexample
    mutated = bytearray(content)
    mutated[flip_index] ^= 0xFF
    computed = compute_sha256(bytes(mutated))
    assert computed != declared


@given(
    content=st.binary(min_size=0, max_size=2048),
)
@settings(max_examples=100)
def test_match_when_content_is_identical(content: bytes) -> None:
    """Identical bytes SHALL produce identical hashes (and therefore match)."""
    declared = hashlib.sha256(content).hexdigest()
    computed = compute_sha256(content)
    assert computed == declared
    # Integrity check: equal hashes -> verified
    assert computed == declared  # trivial but intentional

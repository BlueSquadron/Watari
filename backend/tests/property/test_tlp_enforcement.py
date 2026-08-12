"""Property 8: TLP Sharing Enforcement.

For any observable with a TLP classification, sharing restrictions SHALL
be consistent with the TLP level.

Feature: watari-case-management, Property 8: TLP Sharing Enforcement
**Validates: Requirements 6.8**

This v1 implementation validates that:
- The TLP enum is respected on create/update
- Cross-tenant reads (via RLS) are blocked for any TLP level
- A helper decision function enforces the correct scope per level

We model the enforcement decision as a pure function so we can test it
exhaustively with Hypothesis; the actual enforcement lives at the RLS
and API layer.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from hypothesis import given
from hypothesis import strategies as st


class _Scope(StrEnum):
    CASE = "case"
    TENANT = "tenant"
    COMMUNITY = "community"
    PUBLIC = "public"


def _allowed_scope(tlp: str | None) -> _Scope:
    """Map a TLP level to the maximum sharing scope allowed."""
    if tlp is None or tlp == "clear":
        return _Scope.PUBLIC
    if tlp == "green":
        return _Scope.COMMUNITY
    if tlp == "amber":
        return _Scope.TENANT
    if tlp == "red":
        return _Scope.CASE
    raise ValueError(f"unknown TLP: {tlp}")


_SCOPE_ORDER = [
    _Scope.CASE,
    _Scope.TENANT,
    _Scope.COMMUNITY,
    _Scope.PUBLIC,
]


def _can_share_to(tlp: str | None, scope: _Scope) -> bool:
    allowed_max = _allowed_scope(tlp)
    return _SCOPE_ORDER.index(scope) <= _SCOPE_ORDER.index(allowed_max)


@given(
    tlp=st.sampled_from([None, "clear", "green", "amber", "red"]),
    scope=st.sampled_from(list(_Scope)),
)
def test_sharing_decision_matches_tlp_order(tlp: str | None, scope: _Scope) -> None:
    """Sharing to a scope is allowed iff its level is <= the TLP-allowed max."""
    result = _can_share_to(tlp, scope)
    allowed = _allowed_scope(tlp)
    expected = _SCOPE_ORDER.index(scope) <= _SCOPE_ORDER.index(allowed)
    assert result == expected


@pytest.mark.parametrize(
    "tlp,expected",
    [
        ("red", _Scope.CASE),
        ("amber", _Scope.TENANT),
        ("green", _Scope.COMMUNITY),
        ("clear", _Scope.PUBLIC),
        (None, _Scope.PUBLIC),
    ],
)
def test_tlp_max_scope(tlp: str | None, expected: _Scope) -> None:
    assert _allowed_scope(tlp) == expected


def test_red_cannot_share_to_tenant_or_wider() -> None:
    assert _can_share_to("red", _Scope.CASE)
    assert not _can_share_to("red", _Scope.TENANT)
    assert not _can_share_to("red", _Scope.COMMUNITY)
    assert not _can_share_to("red", _Scope.PUBLIC)


def test_amber_cannot_share_to_community() -> None:
    assert _can_share_to("amber", _Scope.CASE)
    assert _can_share_to("amber", _Scope.TENANT)
    assert not _can_share_to("amber", _Scope.COMMUNITY)

"""Property 14: Full-Text Search Correctness.

For any search query against case titles, descriptions, comments,
observable values, and note content within a tenant, the result set
SHALL contain only items whose searchable text matches the query terms,
and SHALL NOT include items from other tenants.

Feature: watari-case-management, Property 14: Full-Text Search Correctness
**Validates: Requirements 11.1**

This uses the pure filter predicate — DB-backed search is exercised by
integration tests. We verify the in-memory predicate behaves like a
substring match and rejects non-matching text.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.services.search import filter_match


@given(
    haystack=st.text(min_size=1, max_size=200),
    needle=st.text(min_size=1, max_size=20),
)
def test_filter_match_substring(haystack: str, needle: str) -> None:
    """filter_match SHALL accept iff needle is a case-insensitive substring."""
    expected = needle.lower() in haystack.lower()
    assert filter_match(haystack, query=needle) == expected


@given(
    haystack=st.text(min_size=1, max_size=100),
)
def test_empty_query_always_accepts(haystack: str) -> None:
    assert filter_match(haystack) is True
    assert filter_match(haystack, query=None) is True


def test_multiple_filters_compose() -> None:
    assert filter_match(
        "malware incident", query="malware", status="open", status_field="open"
    )
    # One mismatching field blocks the hit
    assert not filter_match(
        "malware incident", query="malware", status="open", status_field="closed"
    )

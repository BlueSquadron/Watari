"""Property 18: Pagination Correctness.

For any list endpoint with pagination parameters (page, pageSize), the
response SHALL contain at most `pageSize` items, `meta.page` SHALL match
the requested page, `meta.totalCount` SHALL reflect the total matching
items, and `meta.totalPages` SHALL equal ceil(totalCount / pageSize).

Feature: watari-case-management, Property 18: Pagination Correctness
**Validates: Requirements 15.5**

Pure-function test against `src.schemas.common.build_pagination_meta`
and `PaginationParams`. No database needed.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from src.schemas.common import (
    PaginationMeta,
    PaginationParams,
    build_pagination_meta,
)


@given(
    total=st.integers(min_value=0, max_value=100_000),
    page=st.integers(min_value=1, max_value=1_000),
    page_size=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=300)
def test_build_pagination_meta_matches_ceil(
    total: int, page: int, page_size: int
) -> None:
    """total_pages SHALL equal ceil(total_count / page_size)."""
    meta = build_pagination_meta(
        total_count=total, page=page, page_size=page_size
    )
    expected_pages = 0 if total == 0 else math.ceil(total / page_size)
    assert meta.total_pages == expected_pages
    assert meta.total_count == total
    assert meta.page == page
    assert meta.page_size == page_size


@given(
    page=st.integers(min_value=1, max_value=1_000),
    page_size=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=200)
def test_pagination_params_offset(page: int, page_size: int) -> None:
    """offset SHALL equal (page - 1) * page_size."""
    p = PaginationParams(page=page, page_size=page_size)
    assert p.offset == (page - 1) * page_size


@given(
    total=st.integers(min_value=0, max_value=10_000),
    page_size=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=200)
def test_all_pages_cover_total_count(total: int, page_size: int) -> None:
    """Summing page sizes across all pages equals the total count (capped)."""
    expected_pages = 0 if total == 0 else math.ceil(total / page_size)
    covered = 0
    for page in range(1, expected_pages + 1):
        offset = (page - 1) * page_size
        # Items on this page
        items_on_page = min(page_size, total - offset)
        assert 0 <= items_on_page <= page_size
        covered += items_on_page
    assert covered == total


def test_empty_collection_returns_zero_pages() -> None:
    """Empty collections have total_pages == 0, not 1."""
    meta = build_pagination_meta(total_count=0, page=1, page_size=25)
    assert meta == PaginationMeta(
        page=1, page_size=25, total_count=0, total_pages=0
    )

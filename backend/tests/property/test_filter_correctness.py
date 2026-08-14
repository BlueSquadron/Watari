"""Property 10: Filter Correctness.

For any filterable view and any combination of applied filter criteria,
every item in the result set SHALL satisfy ALL applied filter conditions,
and no item satisfying all conditions SHALL be excluded.

Feature: watari-case-management, Property 10: Filter Correctness
**Validates: Requirements 8.5, 11.2, 12.5, 13.4, 19.6, 22.5, 23.6**

Pure in-memory tests of the filter predicate against randomly generated
item collections.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.services.search import filter_match


@given(
    items=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=50),
            st.sampled_from(["open", "closed", "pending"]),
            st.sampled_from(["critical", "high", "medium", "low", "informational"]),
        ),
        min_size=0,
        max_size=50,
    ),
    query=st.one_of(st.none(), st.text(min_size=1, max_size=10)),
    status=st.one_of(st.none(), st.sampled_from(["open", "closed", "pending"])),
    severity=st.one_of(st.none(), st.sampled_from(["critical", "high", "low"])),
)
def test_every_filtered_item_satisfies_all_conditions(
    items: list[tuple[str, str, str]],
    query: str | None,
    status: str | None,
    severity: str | None,
) -> None:
    """Every item kept by the filter SHALL satisfy every applied predicate.

    AND every item satisfying all conditions SHALL appear in the result.
    """
    filtered = [
        item
        for item in items
        if filter_match(
            item[0],
            query=query,
            status=status,
            status_field=item[1],
            severity=severity,
            severity_field=item[2],
        )
    ]

    # Invariant 1: each item in the result satisfies all conditions
    for value, item_status, item_severity in filtered:
        if query:
            assert query.lower() in value.lower()
        if status:
            assert item_status == status
        if severity:
            assert item_severity == severity

    # Invariant 2: no item outside the result satisfies all conditions
    for value, item_status, item_severity in items:
        matches = (
            (not query or query.lower() in value.lower())
            and (not status or item_status == status)
            and (not severity or item_severity == severity)
        )
        if matches:
            assert (value, item_status, item_severity) in filtered


def test_empty_result_when_no_items() -> None:
    filtered = [i for i in [] if filter_match(i, query="x")]
    assert filtered == []

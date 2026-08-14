"""Property 27: ATT&CK Heatmap Computation.

For any set of ATT&CK mappings within a tenant, the heatmap SHALL
correctly compute the frequency (count of cases mapped) and maximum
severity for each technique.

Feature: watari-case-management, Property 27: ATT&CK Heatmap Computation
**Validates: Requirements 22.2, 22.3**

Pure function tests against `attack.compute_heatmap_cells`.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.attack import compute_heatmap_cells

_SEVERITIES = ["critical", "high", "medium", "low", "informational"]
_SEVERITY_RANK = {s: i for i, s in enumerate(reversed(_SEVERITIES))}


@given(
    mappings=st.lists(
        st.tuples(
            st.sampled_from(["TA0001", "TA0002", "TA0003"]),
            st.sampled_from(["T1001", "T1002", "T1003"]),
            st.one_of(st.none(), st.uuids()),
            st.one_of(st.none(), st.sampled_from(_SEVERITIES)),
        ),
        min_size=0,
        max_size=30,
    )
)
@settings(max_examples=100)
def test_case_count_equals_distinct_case_ids(
    mappings: list[tuple[str, str, UUID | None, str | None]],
) -> None:
    """For every cell, case_count SHALL equal the number of distinct case_ids."""
    cells = compute_heatmap_cells(mappings)
    for cell in cells:
        key = (cell.tactic_id, cell.technique_id)
        related = {
            case_id
            for tactic, technique, case_id, _sev in mappings
            if (tactic, technique) == key and case_id is not None
        }
        assert cell.case_count == len(related)


@given(
    mappings=st.lists(
        st.tuples(
            st.sampled_from(["TA0001", "TA0002"]),
            st.sampled_from(["T1001", "T1002"]),
            st.one_of(st.none(), st.uuids()),
            st.one_of(st.none(), st.sampled_from(_SEVERITIES)),
        ),
        min_size=1,
        max_size=30,
    )
)
@settings(max_examples=100)
def test_max_severity_is_actually_max(
    mappings: list[tuple[str, str, UUID | None, str | None]],
) -> None:
    """Each cell's max_severity SHALL be the highest severity among its mappings."""
    cells = compute_heatmap_cells(mappings)
    for cell in cells:
        key = (cell.tactic_id, cell.technique_id)
        severities = [
            sev
            for tactic, technique, _case_id, sev in mappings
            if (tactic, technique) == key and sev is not None
        ]
        if not severities:
            assert cell.max_severity is None
        else:
            expected = max(severities, key=_SEVERITY_RANK.get)  # type: ignore[arg-type]
            assert cell.max_severity == expected


def test_empty_input_produces_no_cells() -> None:
    assert compute_heatmap_cells([]) == []


def test_same_case_same_technique_counts_once() -> None:
    case_id = uuid4()
    cells = compute_heatmap_cells(
        [
            ("TA0001", "T1001", case_id, "high"),
            ("TA0001", "T1001", case_id, "high"),  # duplicate
            ("TA0001", "T1001", case_id, "low"),
        ]
    )
    assert len(cells) == 1
    assert cells[0].case_count == 1
    assert cells[0].max_severity == "high"

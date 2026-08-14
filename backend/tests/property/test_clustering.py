"""Property 11: Temporal Clustering Detection.

For any set of timeline entries, the temporal clustering algorithm SHALL
identify groups of events where the inter-event time is below the
clustering threshold, and SHALL NOT group events separated by more than
the threshold into the same cluster.

Feature: watari-case-management, Property 11: Temporal Clustering Detection
**Validates: Requirements 8.9**

Pure function tests — no database required.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.clustering import find_clusters


@dataclass(frozen=True)
class _Entry:
    id: UUID
    event_timestamp: datetime


def _make(offsets: list[int]) -> list[_Entry]:
    base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    return [_Entry(id=uuid4(), event_timestamp=base + timedelta(seconds=o)) for o in offsets]


@given(
    threshold=st.integers(min_value=1, max_value=600),
    gaps=st.lists(st.integers(min_value=0, max_value=2000), min_size=0, max_size=15),
)
@settings(max_examples=200)
def test_events_within_threshold_cluster(threshold: int, gaps: list[int]) -> None:
    """Events whose inter-event gap <= threshold SHALL share a cluster."""
    # Build offsets: cumulative sum so "gaps" is the gap between consecutive events
    offsets = []
    acc = 0
    for g in gaps:
        acc += g
        offsets.append(acc)
    entries = _make(offsets)

    clusters = find_clusters(entries, threshold_seconds=threshold)

    # For each cluster, every adjacent pair SHALL have gap <= threshold
    for c in clusters:
        # Re-derive the sorted times of members
        member_ids = set(c.entry_ids)
        members = [e for e in entries if e.id in member_ids]
        members.sort(key=lambda e: e.event_timestamp)
        for a, b in zip(members, members[1:], strict=False):
            diff = (b.event_timestamp - a.event_timestamp).total_seconds()
            assert diff <= threshold, (
                f"Cluster contains events {diff}s apart with threshold {threshold}"
            )


@given(
    threshold=st.integers(min_value=1, max_value=100),
    gaps=st.lists(st.integers(min_value=0, max_value=500), min_size=1, max_size=15),
)
@settings(max_examples=200)
def test_events_beyond_threshold_split_clusters(
    threshold: int, gaps: list[int]
) -> None:
    """Any two events separated by > threshold SHALL NOT share a cluster."""
    offsets = []
    acc = 0
    for g in gaps:
        acc += g
        offsets.append(acc)
    entries = _make(offsets)

    clusters = find_clusters(entries, threshold_seconds=threshold)

    # Map each entry to its cluster id (or None)
    entry_to_cluster: dict[UUID, int | None] = {e.id: None for e in entries}
    for idx, c in enumerate(clusters):
        for eid in c.entry_ids:
            entry_to_cluster[eid] = idx

    entries_sorted = sorted(entries, key=lambda e: e.event_timestamp)
    for a, b in zip(entries_sorted, entries_sorted[1:], strict=False):
        gap = (b.event_timestamp - a.event_timestamp).total_seconds()
        if gap > threshold:
            # They MUST NOT be in the same cluster (but might both be unclustered)
            ca = entry_to_cluster[a.id]
            cb = entry_to_cluster[b.id]
            if ca is not None and cb is not None:
                assert ca != cb


def test_empty_input_produces_no_clusters() -> None:
    assert find_clusters([], threshold_seconds=60) == []


def test_single_event_produces_no_clusters() -> None:
    """A solitary event should not form a cluster (no visual signal)."""
    clusters = find_clusters(_make([0]), threshold_seconds=60)
    assert clusters == []


def test_dense_events_form_single_cluster() -> None:
    """Three events each 10s apart with a 60s threshold form one cluster."""
    clusters = find_clusters(_make([0, 10, 20]), threshold_seconds=60)
    assert len(clusters) == 1
    assert len(clusters[0].entry_ids) == 3

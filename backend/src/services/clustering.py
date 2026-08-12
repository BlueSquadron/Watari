"""Temporal clustering for timeline visualization.

Groups timeline events into clusters based on inter-event time. Two
events belong to the same cluster if they are separated by less than
`threshold_seconds`; longer gaps start a new cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID


class _Timed(Protocol):
    id: UUID
    event_timestamp: datetime


@dataclass(frozen=True, slots=True)
class Cluster:
    start: datetime
    end: datetime
    entry_ids: tuple[UUID, ...]


def find_clusters(
    entries: list[_Timed], *, threshold_seconds: int = 300
) -> list[Cluster]:
    """Return clusters of events separated by less than the threshold.

    Sorted by timestamp ascending. Singleton clusters are omitted because
    they carry no visual signal — only groups of 2+ events are returned.
    """
    if not entries:
        return []
    sorted_entries = sorted(entries, key=lambda e: e.event_timestamp)
    threshold = timedelta(seconds=threshold_seconds)

    clusters: list[Cluster] = []
    current: list[_Timed] = [sorted_entries[0]]

    def _flush() -> None:
        if len(current) >= 2:
            clusters.append(
                Cluster(
                    start=current[0].event_timestamp,
                    end=current[-1].event_timestamp,
                    entry_ids=tuple(e.id for e in current),
                )
            )

    for entry in sorted_entries[1:]:
        gap = entry.event_timestamp - current[-1].event_timestamp
        if gap <= threshold:
            current.append(entry)
        else:
            _flush()
            current = [entry]
    _flush()
    return clusters


__all__ = ["Cluster", "find_clusters"]

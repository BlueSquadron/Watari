"""Property 29: Geographic Clustering.

For any set of geolocated observables, markers within the same geographic
region (as defined by the current zoom level's clustering radius) SHALL
be grouped into a single cluster marker at low zoom levels, and SHALL be
displayed individually when the zoom level exceeds the clustering
threshold.

Feature: watari-case-management, Property 29: Geographic Clustering
**Validates: Requirements 23.7**

Pure function tests — no database required.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.geospatial import (
    GeoPoint,
    cluster_points,
    cluster_radius_km,
    haversine_km,
)


def _lat() -> st.SearchStrategy[float]:
    return st.floats(
        min_value=-80.0, max_value=80.0, allow_nan=False, allow_infinity=False
    )


def _lng() -> st.SearchStrategy[float]:
    return st.floats(
        min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False
    )


def _points(max_size: int = 15) -> st.SearchStrategy[list[GeoPoint]]:
    return st.lists(
        st.builds(GeoPoint, latitude=_lat(), longitude=_lng()),
        min_size=0,
        max_size=max_size,
    )


@given(points=_points(), zoom=st.integers(min_value=15, max_value=22))
@settings(max_examples=100)
def test_high_zoom_produces_singleton_clusters(
    points: list[GeoPoint], zoom: int
) -> None:
    """At high zoom (> configured max), every point is its own cluster."""
    clusters = cluster_points(
        [(i, p) for i, p in enumerate(points)], zoom=zoom
    )
    assert cluster_radius_km(zoom) == 0.0
    assert len(clusters) == len(points)
    for c in clusters:
        assert len(c.point_ids) == 1


@given(points=_points(), zoom=st.integers(min_value=0, max_value=11))
@settings(max_examples=100)
def test_every_point_belongs_to_exactly_one_cluster(
    points: list[GeoPoint], zoom: int
) -> None:
    """At any reasonable zoom level, each point ends up in exactly one cluster."""
    clusters = cluster_points(
        [(i, p) for i, p in enumerate(points)], zoom=zoom
    )
    assigned = [pid for c in clusters for pid in c.point_ids]
    expected = list(range(len(points)))
    assert sorted(assigned) == expected


def test_points_closer_than_radius_merge() -> None:
    """Two points within the radius SHALL share a single cluster."""
    zoom = 4  # 250 km radius
    p1 = GeoPoint(latitude=48.8566, longitude=2.3522)  # Paris
    p2 = GeoPoint(latitude=48.86, longitude=2.35)  # few blocks away
    clusters = cluster_points([(0, p1), (1, p2)], zoom=zoom)
    assert len(clusters) == 1
    assert sorted(clusters[0].point_ids) == [0, 1]


def test_points_far_apart_do_not_merge() -> None:
    """Points outside the radius SHALL remain in separate clusters."""
    zoom = 4  # 250 km radius
    paris = GeoPoint(latitude=48.8566, longitude=2.3522)
    tokyo = GeoPoint(latitude=35.6762, longitude=139.6503)
    clusters = cluster_points([(0, paris), (1, tokyo)], zoom=zoom)
    assert len(clusters) == 2


@given(zoom=st.integers(min_value=0, max_value=11))
def test_cluster_radius_is_monotonically_non_increasing(zoom: int) -> None:
    """As zoom increases, the clustering radius SHALL not grow."""
    if zoom == 0:
        return
    assert cluster_radius_km(zoom) <= cluster_radius_km(zoom - 1)

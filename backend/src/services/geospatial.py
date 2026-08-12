"""Pure geospatial helpers used by the geospatial API and tests.

Keeping these as plain functions (no DB dependency) lets us exercise
Properties 28 and 29 exhaustively with Hypothesis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


# Equirectangular precision used to express "marker positioning accuracy"
# (Property 28). Rounding degrees to 4 decimals gives ~11m resolution
# at the equator, well within the <1km tolerance the requirement asks for.
_COORD_ROUNDING = 4


@dataclass(frozen=True, slots=True)
class GeoPoint:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class Cluster:
    latitude: float
    longitude: float
    point_ids: tuple[int, ...]


def normalize_marker(lat: float, lng: float) -> GeoPoint:
    """Validate + round a (lat, lng) pair to the canonical precision.

    Raises ``ValueError`` if the coordinate is outside the valid range.
    """
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"latitude {lat} out of range")
    if not -180.0 <= lng <= 180.0:
        raise ValueError(f"longitude {lng} out of range")
    return GeoPoint(
        latitude=round(float(lat), _COORD_ROUNDING),
        longitude=round(float(lng), _COORD_ROUNDING),
    )


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Great-circle distance in kilometres between two points."""
    r_earth_km = 6371.0088
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    d_lat = math.radians(b.latitude - a.latitude)
    d_lng = math.radians(b.longitude - a.longitude)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * r_earth_km * math.asin(math.sqrt(h))


# Distance thresholds (km) per zoom level. Very low zoom groups into
# continents; very high zoom effectively disables clustering.
_ZOOM_RADIUS_KM: dict[int, float] = {
    0: 5000.0,
    1: 2500.0,
    2: 1000.0,
    3: 500.0,
    4: 250.0,
    5: 100.0,
    6: 50.0,
    7: 25.0,
    8: 10.0,
    9: 5.0,
    10: 2.0,
    11: 1.0,
}

_MAX_ZOOM_FOR_CLUSTERING = max(_ZOOM_RADIUS_KM)


def cluster_radius_km(zoom: int) -> float:
    """Return the clustering radius for the given zoom level.

    At zoom levels above ``_MAX_ZOOM_FOR_CLUSTERING`` we return 0, which
    effectively disables clustering — every marker renders individually.
    """
    if zoom > _MAX_ZOOM_FOR_CLUSTERING:
        return 0.0
    if zoom < 0:
        return _ZOOM_RADIUS_KM[0]
    # Linearly interpolate for zoom values between known anchors
    return _ZOOM_RADIUS_KM.get(zoom, _ZOOM_RADIUS_KM[max(_ZOOM_RADIUS_KM)])


def cluster_points(
    points: list[tuple[int, GeoPoint]], zoom: int
) -> list[Cluster]:
    """Group points that fall within ``cluster_radius_km(zoom)`` of each other.

    Uses a greedy single-linkage approach: iterate sorted points, each
    point either joins the first existing cluster within the radius or
    starts a new one. The centroid is the arithmetic mean of constituents.
    Deterministic in input order for test reproducibility.
    """
    radius = cluster_radius_km(zoom)
    clusters: list[list[tuple[int, GeoPoint]]] = []
    for pid, pt in points:
        if radius <= 0:
            clusters.append([(pid, pt)])
            continue
        placed = False
        for group in clusters:
            centroid = _centroid([p for _, p in group])
            if haversine_km(centroid, pt) <= radius:
                group.append((pid, pt))
                placed = True
                break
        if not placed:
            clusters.append([(pid, pt)])

    return [
        Cluster(
            latitude=_centroid([p for _, p in group]).latitude,
            longitude=_centroid([p for _, p in group]).longitude,
            point_ids=tuple(pid for pid, _ in group),
        )
        for group in clusters
    ]


def _centroid(points: list[GeoPoint]) -> GeoPoint:
    lat = sum(p.latitude for p in points) / len(points)
    lng = sum(p.longitude for p in points) / len(points)
    return GeoPoint(latitude=lat, longitude=lng)


__all__ = [
    "GeoPoint",
    "Cluster",
    "cluster_points",
    "cluster_radius_km",
    "haversine_km",
    "normalize_marker",
]

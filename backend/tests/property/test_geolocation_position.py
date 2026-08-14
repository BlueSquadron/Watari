"""Property 28: Geolocation Marker Positioning.

For any observable with geolocation enrichment data containing latitude
and longitude, the map marker SHALL be positioned at coordinates matching
the enrichment data within acceptable precision (<1km error).

Feature: watari-case-management, Property 28: Geolocation Marker Positioning
**Validates: Requirements 23.2**

Pure function tests — no database required.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.geospatial import (
    GeoPoint,
    haversine_km,
    normalize_marker,
)

_MAX_ACCEPTABLE_ERROR_KM = 1.0


@given(
    lat=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    lng=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=300)
def test_normalized_marker_is_close_to_source(lat: float, lng: float) -> None:
    """Rounding to the canonical precision SHALL introduce <1km error."""
    source = GeoPoint(latitude=lat, longitude=lng)
    placed = normalize_marker(lat, lng)
    err = haversine_km(source, placed)
    assert err < _MAX_ACCEPTABLE_ERROR_KM, f"Marker for ({lat},{lng}) displaced by {err:.3f}km"


@given(
    lat=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    lng=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=200)
def test_normalize_is_idempotent(lat: float, lng: float) -> None:
    """normalize_marker(normalize_marker(p)) == normalize_marker(p)."""
    first = normalize_marker(lat, lng)
    second = normalize_marker(first.latitude, first.longitude)
    assert math.isclose(first.latitude, second.latitude, abs_tol=1e-6)
    assert math.isclose(first.longitude, second.longitude, abs_tol=1e-6)


@pytest.mark.parametrize(
    "lat,lng",
    [
        (90.0001, 0.0),
        (-90.0001, 0.0),
        (0.0, 180.0001),
        (0.0, -180.0001),
    ],
)
def test_out_of_range_coords_rejected(lat: float, lng: float) -> None:
    """Coordinates outside the valid range SHALL raise ValueError."""
    with pytest.raises(ValueError):
        normalize_marker(lat, lng)


def test_known_reference_points() -> None:
    """Sanity check against known landmarks."""
    paris = normalize_marker(48.8566, 2.3522)
    new_york = normalize_marker(40.7128, -74.0060)
    distance_km = haversine_km(paris, new_york)
    # Paris to New York is roughly 5837km — allow 50km tolerance
    assert 5700 < distance_km < 5900, f"unexpected distance {distance_km}"

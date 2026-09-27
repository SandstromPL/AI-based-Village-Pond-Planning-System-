"""Unit tests for the Overpass land-use provider and the constraint service
that projects/buffers/unions its geometries for candidate filtering."""

from unittest.mock import Mock, patch

import httpx
import pytest
from shapely.geometry import Point

from app.config import settings
from app.models.contour import BoundingBox
from app.providers.landuse.overpass import clear_landuse_cache, fetch_exclusion_geometries
from app.services.landuse_service import build_exclusion_union

_BBOX = BoundingBox(min_lon=81.28, min_lat=21.26, max_lon=81.29, max_lat=21.27)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_landuse_cache()
    yield
    clear_landuse_cache()


def _overpass_response(elements):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"elements": elements}
    return response


def _way(tags, coords):
    """A minimal Overpass `out geom;` way element."""
    return {
        "type": "way",
        "id": 1,
        "tags": tags,
        "geometry": [{"lat": lat, "lon": lon} for lon, lat in coords],
    }


# A small square "building" footprint near the bbox centre.
_BUILDING_COORDS = [
    (81.2849, 21.2649),
    (81.2851, 21.2649),
    (81.2851, 21.2651),
    (81.2849, 21.2651),
    (81.2849, 21.2649),
]


@patch("app.providers.landuse.overpass.httpx.post")
def test_fetch_exclusion_geometries_categorizes_by_tag(mock_post):
    road_coords = [(81.280, 21.260), (81.281, 21.261)]
    mock_post.return_value = _overpass_response([
        _way({"building": "yes"}, _BUILDING_COORDS),
        _way({"highway": "residential"}, road_coords),
    ])

    layers = fetch_exclusion_geometries(_BBOX)

    assert layers.status == "success"
    assert len(layers.buildings) == 1
    assert len(layers.roads) == 1
    assert len(layers.waterways) == 0


@patch("app.providers.landuse.overpass.httpx.post")
def test_fetch_exclusion_geometries_skips_relations_and_malformed_ways(mock_post):
    mock_post.return_value = _overpass_response([
        {"type": "relation", "id": 2, "tags": {"natural": "water"}},
        {"type": "way", "id": 3, "tags": {"building": "yes"}, "geometry": None},
    ])

    layers = fetch_exclusion_geometries(_BBOX)

    assert layers.status == "success"
    assert layers.buildings == []
    assert layers.water_bodies == []


@patch("app.providers.landuse.overpass.httpx.post")
def test_fetch_exclusion_geometries_returns_unavailable_on_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timed out")

    layers = fetch_exclusion_geometries(_BBOX)

    assert layers.status == "unavailable"


@patch("app.providers.landuse.overpass.httpx.post")
def test_fetch_exclusion_geometries_does_not_retry_connect_errors(mock_post):
    """A DNS/connection failure should not be retried — same reasoning as
    the elevation provider cascade (see test_elevation_provider.py): a
    same-second retry essentially never succeeds if DNS itself is broken,
    and a real production log showed this doubling Overpass's failure time
    from ~20s to ~40s for no benefit."""
    mock_post.side_effect = httpx.ConnectError("Temporary failure in name resolution")

    layers = fetch_exclusion_geometries(_BBOX)

    assert layers.status == "unavailable"
    assert mock_post.call_count == 1  # overpass_max_retries allows 2, but must stop after 1


@patch("app.providers.landuse.overpass.httpx.post")
def test_fetch_exclusion_geometries_does_not_cache_failures(mock_post):
    """A transient failure must not permanently disable the filter for this
    bbox — only successful results are cached, so a retry can succeed."""
    mock_post.side_effect = httpx.TimeoutException("timed out")
    first = fetch_exclusion_geometries(_BBOX)
    assert first.status == "unavailable"

    mock_post.side_effect = None
    mock_post.return_value = _overpass_response([_way({"building": "yes"}, _BUILDING_COORDS)])
    second = fetch_exclusion_geometries(_BBOX)

    assert second.status == "success"
    assert mock_post.call_count == 3  # 2 failed attempts + 1 fresh successful attempt


@patch("app.providers.landuse.overpass.httpx.post")
def test_build_exclusion_union_flags_point_inside_building(mock_post):
    mock_post.return_value = _overpass_response([_way({"building": "yes"}, _BUILDING_COORDS)])

    projected_crs = "EPSG:32644"  # UTM zone covering this area
    union, warnings = build_exclusion_union(_BBOX, projected_crs)

    assert union is not None
    assert warnings == []

    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)
    inside_x, inside_y = transformer.transform(81.2850, 21.2650)
    far_x, far_y = transformer.transform(81.35, 21.35)

    assert Point(inside_x, inside_y).intersects(union)
    assert not Point(far_x, far_y).intersects(union)


@patch("app.providers.landuse.overpass.httpx.post")
def test_build_exclusion_union_degrades_gracefully_on_overpass_failure(mock_post):
    mock_post.side_effect = httpx.ConnectError("network is unreachable")

    union, warnings = build_exclusion_union(_BBOX, "EPSG:32644")

    assert union is None
    assert len(warnings) == 1
    assert "skipped" in warnings[0].lower()


@patch("app.providers.landuse.overpass.httpx.post")
def test_build_exclusion_union_noop_when_disabled(mock_post):
    original = settings.landuse_constraint_enabled
    settings.landuse_constraint_enabled = False
    try:
        union, warnings = build_exclusion_union(_BBOX, "EPSG:32644")
        assert union is None
        assert warnings == []
        mock_post.assert_not_called()
    finally:
        settings.landuse_constraint_enabled = original

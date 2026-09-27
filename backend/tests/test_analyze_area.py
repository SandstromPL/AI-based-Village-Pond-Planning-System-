"""Integration test for the map-selected-area analysis endpoint."""

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.elevation.open_elevation import clear_elevation_cache
from app.providers.landuse.overpass import clear_landuse_cache
from app.services.rainfall_service import clear_rainfall_cache

client = TestClient(app)

# Small square (~600 m) polygon in EPSG:4326 over a synthetic bowl-shaped
# terrain, so depression-filling/candidate generation has something to find.
_CENTER_LAT = 21.2632
_CENTER_LON = 81.2828
_HALF_SIDE_DEG = 0.003  # ~330 m

_POLYGON = [
    [_CENTER_LON - _HALF_SIDE_DEG, _CENTER_LAT - _HALF_SIDE_DEG],
    [_CENTER_LON + _HALF_SIDE_DEG, _CENTER_LAT - _HALF_SIDE_DEG],
    [_CENTER_LON + _HALF_SIDE_DEG, _CENTER_LAT + _HALF_SIDE_DEG],
    [_CENTER_LON - _HALF_SIDE_DEG, _CENTER_LAT + _HALF_SIDE_DEG],
]


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_elevation_cache()
    clear_rainfall_cache()
    clear_landuse_cache()
    yield
    clear_elevation_cache()
    clear_rainfall_cache()
    clear_landuse_cache()


def _bowl_elevation_response(url, json=None, timeout=None, **kwargs):
    results = []
    for loc in json["locations"]:
        dlat = loc["latitude"] - _CENTER_LAT
        dlon = loc["longitude"] - _CENTER_LON
        elevation = 100.0 + (dlat ** 2 + dlon ** 2) * 300_000.0
        results.append({"elevation": elevation})
    return httpx.Response(
        200, json={"results": results}, request=httpx.Request("POST", url)
    )


def _empty_overpass_response(url, data=None, timeout=None, **kwargs):
    return httpx.Response(200, json={"elements": []}, request=httpx.Request("POST", url))


def _combined_post_response(url, json=None, data=None, timeout=None, **kwargs):
    # httpx.post is a single shared global target — both the elevation
    # provider and the Overpass land-use provider call it, so one mock
    # must dispatch on the request shape (elevation sends json=, Overpass
    # sends form-encoded data=) rather than assuming only one caller.
    if json is not None and "locations" in json:
        return _bowl_elevation_response(url, json=json, timeout=timeout, **kwargs)
    return _empty_overpass_response(url, data=data, timeout=timeout, **kwargs)


def _rainfall_response(url, params=None, timeout=None, **kwargs):
    body = {
        "daily": {
            "time": ["2023-06-01", "2023-07-01", "2024-06-01", "2024-07-01"],
            "precipitation_sum": [200.0, 250.0, 210.0, 240.0],
        }
    }
    return httpx.Response(200, json=body, request=httpx.Request("GET", url))


@patch("app.services.rainfall_service.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_analyze_area_returns_full_pipeline_output(mock_post, mock_get):
    mock_post.side_effect = _combined_post_response
    mock_get.side_effect = _rainfall_response

    resp = client.post("/api/v1/analyzeArea", json={"polygon": _POLYGON})

    assert resp.status_code == 200, resp.text[:500]
    data = resp.json()

    assert data["input"]["source_type"] == "selected_area"
    assert data["input"]["filename"] is None
    assert data["terrain"]["grid_rows"] > 0
    assert data["rainfall"]["status"] == "success"

    assert data["recommended"] is not None, f"No recommended pond found: {data['warnings']}"
    assert data["recommended"]["expected_annual_collection_m3"] is not None
    assert data["recommended"]["planned_storage_m3"] is not None
    assert data["geojson_layers"]["recommended_location"]["properties"][
        "expected_annual_collection_m3"
    ] is not None


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_analyze_area_rejects_oversized_polygon(mock_post):
    huge_polygon = [[70.0, 10.0], [80.0, 10.0], [80.0, 20.0], [70.0, 20.0]]
    resp = client.post("/api/v1/analyzeArea", json={"polygon": huge_polygon})
    assert resp.status_code == 400
    mock_post.assert_not_called()


def test_analyze_area_rejects_too_few_points():
    resp = client.post(
        "/api/v1/analyzeArea",
        json={"polygon": [[81.28, 21.26], [81.29, 21.27]]},
    )
    assert resp.status_code == 422

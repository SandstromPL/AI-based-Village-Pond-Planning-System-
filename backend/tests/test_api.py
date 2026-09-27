"""
Integration test for the full analysis API.
Run with: pytest tests/test_api.py -v
"""
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLE_KML = os.path.join(os.path.dirname(__file__), "..", "data", "contours_1m.kml")


def _get_sample_bytes():
    if not os.path.exists(SAMPLE_KML):
        pytest.skip("Sample KML not found. Copy contours_1m.kml to backend/data/")
    with open(SAMPLE_KML, "rb") as f:
        return f.read()


def test_health_endpoint():
    """Health check should return 200 with status ok."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_analyze_contour_returns_200():
    """Full pipeline should complete successfully with the sample KML."""
    kml_bytes = _get_sample_bytes()
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"


def test_analyze_contour_response_structure():
    """Response must contain required top-level keys."""
    kml_bytes = _get_sample_bytes()
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert resp.status_code == 200
    data = resp.json()

    required_keys = [
        "analysis_id", "status", "processing_time_s",
        "input", "terrain", "candidates", "recommended",
        "rainfall", "runoff", "pond", "geojson_layers", "assumptions",
    ]
    for key in required_keys:
        assert key in data, f"Missing key: {key}"


def test_analyze_contour_has_recommended():
    """A recommended pond location should be present."""
    kml_bytes = _get_sample_bytes()
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    data = resp.json()
    assert data["recommended"] is not None, "No recommended pond found"
    rec = data["recommended"]
    assert rec["catchment_area_km2"] > 0
    assert rec["score"] > 0
    assert len(rec["reasoning"]) > 0


def test_analyze_contour_bbox_match():
    """Recommended location should be inside the KML bounding box."""
    kml_bytes = _get_sample_bytes()
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    data = resp.json()
    if data["recommended"] is None:
        pytest.skip("No recommended candidate — skipping bbox check")

    bbox = data["input"]["bbox"]
    loc = data["recommended"]["location"]

    margin = 0.01  # small geographic margin
    assert bbox["min_lon"] - margin <= loc["longitude"] <= bbox["max_lon"] + margin
    assert bbox["min_lat"] - margin <= loc["latitude"] <= bbox["max_lat"] + margin


def test_get_analysis_by_id():
    """GET /analysis/{id} should return the same result as the original POST."""
    kml_bytes = _get_sample_bytes()
    post_resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    analysis_id = post_resp.json()["analysis_id"]

    get_resp = client.get(f"/api/v1/analysis/{analysis_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["analysis_id"] == analysis_id


def test_get_nonexistent_analysis_returns_404():
    """Non-existent analysis ID should return 404."""
    resp = client.get("/api/v1/analysis/does-not-exist-at-all")
    assert resp.status_code == 404


def test_analyze_wrong_file_type_returns_400():
    """Uploading a non-KML file should return 400."""
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("terrain.shp", b"random bytes", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_geojson_layers_present():
    """GeoJSON layers should be valid FeatureCollections."""
    kml_bytes = _get_sample_bytes()
    resp = client.post(
        "/api/v1/analyzeContour",
        files={"file": ("contours_1m.kml", kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    data = resp.json()
    layers = data["geojson_layers"]
    for key in ["contour_lines", "candidates", "recommended_location", "catchment_boundaries"]:
        assert key in layers, f"Missing GeoJSON layer: {key}"

    assert layers["contour_lines"]["type"] == "FeatureCollection"
    assert len(layers["contour_lines"]["features"]) > 0

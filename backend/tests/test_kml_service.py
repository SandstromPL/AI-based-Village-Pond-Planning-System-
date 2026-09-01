"""
Tests for the KML/KMZ parser service.
"""
import os
import pytest
from app.services.kml_service import parse_contour_file, KMLParseError

# Path to the sample KML file
SAMPLE_KML = os.path.join(os.path.dirname(__file__), "..", "data", "contours_1m.kml")


def _load_sample() -> bytes:
    if not os.path.exists(SAMPLE_KML):
        pytest.skip("Sample KML not found. Copy contours_1m.kml to backend/data/")
    with open(SAMPLE_KML, "rb") as f:
        return f.read()


def test_parse_sample_kml_returns_contours():
    """Parsed result should contain multiple contour lines."""
    data = _load_sample()
    result = parse_contour_file(data, "contours_1m.kml")
    assert result.contour_count > 0, "Expected at least 1 contour"


def test_parse_sample_kml_elevation_range():
    """Elevation values should be within a plausible range for Indian terrain."""
    data = _load_sample()
    result = parse_contour_file(data, "contours_1m.kml")
    assert result.min_elevation > 0, "Min elevation should be positive"
    assert result.max_elevation > result.min_elevation
    # Based on the KML sample: elevations ~274-310 m
    assert 100 < result.min_elevation < 500
    assert 100 < result.max_elevation < 600


def test_parse_sample_kml_bbox():
    """Bounding box should be in a valid geographic range."""
    data = _load_sample()
    result = parse_contour_file(data, "contours_1m.kml")
    bbox = result.bbox
    assert -180 <= bbox.min_lon < bbox.max_lon <= 180
    assert -90 <= bbox.min_lat < bbox.max_lat <= 90


def test_parse_sample_kml_coordinates():
    """Every contour should have at least 2 coordinate pairs."""
    data = _load_sample()
    result = parse_contour_file(data, "contours_1m.kml")
    for contour in result.contours:
        assert len(contour.coordinates) >= 2


def test_parse_invalid_file_raises():
    """Garbage bytes should raise KMLParseError."""
    with pytest.raises(KMLParseError):
        parse_contour_file(b"this is not valid kml", "bad.kml")


def test_parse_wrong_extension_raises():
    """Unsupported extension should raise KMLParseError."""
    with pytest.raises(KMLParseError):
        parse_contour_file(b"irrelevant", "file.shp")


def test_parse_empty_file_raises():
    """Empty XML with no Placemarks should raise KMLParseError."""
    empty_kml = b'<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document></Document></kml>'
    with pytest.raises(KMLParseError):
        parse_contour_file(empty_kml, "empty.kml")

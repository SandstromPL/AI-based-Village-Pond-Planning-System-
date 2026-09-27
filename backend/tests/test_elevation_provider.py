"""Unit tests for the Open-Elevation provider: batching, retries, fallback."""

from unittest.mock import Mock, patch

import httpx
import pytest

from app.providers.elevation.open_elevation import (
    clear_elevation_cache,
    fetch_elevations,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_elevation_cache()
    yield
    clear_elevation_cache()


def _mock_response(elevations):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "results": [{"elevation": e} for e in elevations]
    }
    return response


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_returns_values_for_all_points(mock_post):
    mock_post.return_value = _mock_response([100.0, 105.5])

    result = fetch_elevations([(21.26, 81.28), (21.27, 81.29)])

    assert result == [100.0, 105.5]
    assert mock_post.call_count == 1


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_caches_repeated_points(mock_post):
    mock_post.return_value = _mock_response([100.0])

    fetch_elevations([(21.26, 81.28)])
    fetch_elevations([(21.26, 81.28)])

    assert mock_post.call_count == 1


@patch("app.providers.elevation.open_elevation.time.sleep", return_value=None)
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_returns_none_after_persistent_failure(mock_post, _mock_sleep):
    mock_post.side_effect = httpx.TimeoutException("timed out")

    result = fetch_elevations([(21.26, 81.28)])

    assert result == [None]


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_chunks_large_point_lists(mock_post, monkeypatch=None):
    from app.config import settings

    original_batch_size = settings.elevation_batch_size
    settings.elevation_batch_size = 2
    try:
        mock_post.side_effect = [
            _mock_response([1.0, 2.0]),
            _mock_response([3.0]),
        ]
        result = fetch_elevations([(0.0, 0.0), (0.1, 0.1), (0.2, 0.2)])
        assert result == [1.0, 2.0, 3.0]
        assert mock_post.call_count == 2
    finally:
        settings.elevation_batch_size = original_batch_size

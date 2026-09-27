"""Unit tests for the Open-Elevation provider: batching, retries, fallback."""

import time
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
@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_returns_none_after_both_providers_fail(mock_post, mock_get, _mock_sleep):
    mock_post.side_effect = httpx.TimeoutException("timed out")
    mock_get.side_effect = httpx.TimeoutException("timed out")

    result = fetch_elevations([(21.26, 81.28)])

    assert result == [None]


@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_falls_back_to_opentopodata_on_total_failure(mock_post, mock_get):
    mock_post.side_effect = httpx.TimeoutException("timed out")
    mock_get.return_value = _mock_response([250.0])

    result = fetch_elevations([(21.26, 81.28)])

    assert result == [250.0]
    assert mock_get.call_count == 1


@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_respects_total_time_budget(mock_post, mock_get):
    """A slow/failing network must not make the whole fetch scale with
    batch count x retries x providers — the deadline should cut it short."""
    from app.config import settings

    def slow_fail(*args, **kwargs):
        time.sleep(0.05)
        raise httpx.TimeoutException("timed out")

    mock_post.side_effect = slow_fail
    mock_get.side_effect = slow_fail

    original = {
        "elevation_total_budget_s": settings.elevation_total_budget_s,
        "elevation_batch_size": settings.elevation_batch_size,
        "elevation_max_concurrent_requests": settings.elevation_max_concurrent_requests,
    }
    settings.elevation_total_budget_s = 0.2
    settings.elevation_batch_size = 2
    settings.elevation_max_concurrent_requests = 1
    try:
        points = [(i * 0.01, 0.0) for i in range(20)]  # 10 batches of 2, forced sequential
        start = time.monotonic()
        result = fetch_elevations(points)
        elapsed = time.monotonic() - start

        assert result == [None] * 20
        # Without the deadline this would take ~10 batches worth of full
        # retry+fallback chains (several seconds); it must stay well short.
        assert elapsed < 2.0
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


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

"""Unit tests for the elevation provider cascade: OpenZenith (primary),
falling back to Open-Elevation, falling back to OpenTopoData."""

import time
from unittest.mock import Mock, patch

import httpx
import pytest

from app.config import settings
from app.providers.elevation.open_elevation import (
    clear_elevation_cache,
    fetch_elevations,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_elevation_cache()
    yield
    clear_elevation_cache()


def _openzenith_response(batch, elevations):
    """OpenZenith echoes lat/lon per result, unlike the other two providers."""
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "results": [
            {"lat": lat, "lon": lon, "elevation": e}
            for (lat, lon), e in zip(batch, elevations)
        ]
    }
    return response


def _plain_response(elevations):
    """Open-Elevation / OpenTopoData shape: no lat/lon echo."""
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": [{"elevation": e} for e in elevations]}
    return response


def _is_openzenith_call(args, kwargs):
    url = args[0] if args else kwargs.get("url", "")
    return "openzenith" in url


@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_uses_openzenith_first_and_skips_fallback(mock_post, mock_get):
    batch = [(21.26, 81.28), (21.27, 81.29)]
    mock_post.return_value = _openzenith_response(batch, [100.0, 105.5])

    result = fetch_elevations(batch)

    assert result == [100.0, 105.5]
    assert mock_post.call_count == 1
    mock_get.assert_not_called()  # OpenTopoData never needed


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_caches_repeated_points(mock_post):
    batch = [(21.26, 81.28)]
    mock_post.return_value = _openzenith_response(batch, [100.0])

    fetch_elevations(batch)
    fetch_elevations(batch)

    assert mock_post.call_count == 1


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_falls_back_to_open_elevation_when_openzenith_fails(mock_post):
    point = (21.26, 81.28)

    def dispatch(*args, **kwargs):
        if _is_openzenith_call(args, kwargs):
            raise httpx.TimeoutException("openzenith timed out")
        return _plain_response([123.4])

    mock_post.side_effect = dispatch

    result = fetch_elevations([point])

    assert result == [123.4]


@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_falls_back_to_opentopodata_when_post_based_providers_fail(
    mock_post, mock_get
):
    """OpenZenith and Open-Elevation both use httpx.post — a network that
    can't reach either falls through to OpenTopoData (httpx.get)."""
    mock_post.side_effect = httpx.TimeoutException("timed out")
    mock_get.return_value = _plain_response([250.0])

    result = fetch_elevations([(21.26, 81.28)])

    assert result == [250.0]
    assert mock_get.call_count == 1


@patch("app.providers.elevation.open_elevation.time.sleep", return_value=None)
@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_returns_none_after_all_three_providers_fail(mock_post, mock_get, _mock_sleep):
    mock_post.side_effect = httpx.TimeoutException("timed out")
    mock_get.side_effect = httpx.TimeoutException("timed out")

    result = fetch_elevations([(21.26, 81.28)])

    assert result == [None]


@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_respects_total_time_budget(mock_post, mock_get):
    """A slow/failing network must not make the whole fetch scale with
    batch count x retries x providers — the deadline should cut it short."""

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
def test_fetch_elevations_chunks_large_point_lists(mock_post):
    original_batch_size = settings.elevation_batch_size
    settings.elevation_batch_size = 2
    try:
        points = [(0.0, 0.0), (0.1, 0.1), (0.2, 0.2)]
        mock_post.side_effect = [
            _openzenith_response(points[0:2], [1.0, 2.0]),
            _openzenith_response(points[2:3], [3.0]),
        ]
        result = fetch_elevations(points)
        assert result == [1.0, 2.0, 3.0]
        assert mock_post.call_count == 2
    finally:
        settings.elevation_batch_size = original_batch_size

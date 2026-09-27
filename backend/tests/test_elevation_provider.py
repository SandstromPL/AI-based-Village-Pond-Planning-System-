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


@patch("app.providers.elevation.open_elevation.time.sleep", return_value=None)
@patch("app.providers.elevation.open_elevation.httpx.get")
@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_does_not_cache_failures(mock_post, mock_get, _mock_sleep):
    """A point that fails every provider tier must not be cached — a real
    production incident showed the exact same failed points being served
    from cache on every later request, forever, even after the network
    had recovered. Only a real (non-None) value should be cached."""
    point = (21.26, 81.28)

    mock_post.side_effect = httpx.TimeoutException("timed out")
    mock_get.side_effect = httpx.TimeoutException("timed out")
    first = fetch_elevations([point])
    assert first == [None]

    mock_post.side_effect = None
    mock_post.return_value = _openzenith_response([point], [150.0])
    second = fetch_elevations([point])
    assert second == [150.0]  # retried fresh, not served a cached None


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


@patch("app.providers.elevation.open_elevation.httpx.post")
def test_fetch_elevations_does_not_retry_connect_errors(mock_post):
    """A DNS/connection failure should not be retried — a same-second
    retry essentially never succeeds if DNS itself is broken, and (per a
    real production incident) retrying anyway wasted most of the total
    time budget on one provider, leaving the fallback chain almost no
    time to actually rescue those points."""
    point = (21.26, 81.28)
    openzenith_call_count = 0

    def dispatch(*args, **kwargs):
        nonlocal openzenith_call_count
        if _is_openzenith_call(args, kwargs):
            openzenith_call_count += 1
            raise httpx.ConnectError("Temporary failure in name resolution")
        return _plain_response([123.4])

    mock_post.side_effect = dispatch

    result = fetch_elevations([point])

    assert result == [123.4]  # still recovered via the Open-Elevation fallback
    # elevation_max_retries allows 2 attempts, but a ConnectError must stop after 1.
    assert openzenith_call_count == 1


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


def test_fallback_chain_fetches_sub_batches_concurrently():
    """Regression test for a real production bug: when OpenZenith fails a
    large batch, re-chunking it into small Open-Elevation sub-batches and
    fetching them *sequentially* meant most of the deadline could be
    consumed by OpenZenith's own retries before the fallback even started,
    leaving time for only 1-2 of e.g. 20 sequential sub-batch calls —
    turning a recoverable batch into a mostly-missing one and triggering a
    false "elevation unavailable" error. Fetching sub-batches concurrently
    fixes this; this test asserts the wall-clock time reflects
    concurrency, not sequential execution."""
    from app.providers.elevation.open_elevation import _fetch_fallback_chain

    original_sub_size = settings.elevation_fallback_batch_size
    settings.elevation_fallback_batch_size = 10
    try:
        batch = [(21.26 + i * 0.001, 81.28) for i in range(200)]  # 20 sub-batches

        def slow_success(*args, **kwargs):
            time.sleep(0.1)
            sub_batch_size = len(args[1]["locations"]) if len(args) > 1 else 10
            return _plain_response([100.0] * sub_batch_size)

        with patch(
            "app.providers.elevation.open_elevation.httpx.post", side_effect=slow_success
        ):
            deadline = time.monotonic() + 30  # plenty of budget, isolating concurrency itself
            start = time.monotonic()
            result = _fetch_fallback_chain(batch, deadline)
            elapsed = time.monotonic() - start

        assert result == [100.0] * 200
        # Sequential would take ~20 * 0.1s = 2.0s; concurrent (12 workers,
        # 2 waves) should be closer to 0.2-0.3s. Generous bound to avoid
        # flakiness while still catching a regression to sequential.
        assert elapsed < 1.0
    finally:
        settings.elevation_fallback_batch_size = original_sub_size


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

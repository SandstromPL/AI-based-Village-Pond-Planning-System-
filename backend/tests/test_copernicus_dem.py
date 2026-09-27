"""Unit tests for the Copernicus DEM elevation provider — reads static
Cloud-Optimized GeoTIFF tiles from public AWS S3 storage rather than
querying a rate-limited REST API. `rasterio.open` is mocked throughout;
these tests never touch the real network."""

import time
from unittest.mock import Mock, patch

import pytest

from app.config import settings
from app.providers.elevation.copernicus_dem import (
    clear_tile_cache,
    fetch_from_copernicus_dem,
)
from app.utils import circuit_breaker


@pytest.fixture(autouse=True)
def _clear_between_tests():
    clear_tile_cache()
    circuit_breaker.clear_all()
    yield
    clear_tile_cache()
    circuit_breaker.clear_all()


def _mock_dataset(sample_values):
    """A rasterio-dataset-shaped mock: .sample(coords) yields one
    single-element array per coordinate, matching real rasterio behaviour.
    Uses side_effect (a fresh generator per call) rather than a single
    stored return_value, since real rasterio.sample() returns a fresh
    generator every time it's called, not a single-use iterator that
    exhausts after the first call."""
    dataset = Mock()
    dataset.sample.side_effect = lambda coords: iter([[v] for v in sample_values])
    return dataset


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_samples_points_within_a_single_tile(mock_open):
    mock_open.return_value = _mock_dataset([100.0, 105.5])

    result = fetch_from_copernicus_dem(
        [(21.26, 81.28), (21.27, 81.29)], deadline=time.monotonic() + 10
    )

    assert result == [100.0, 105.5]
    assert mock_open.call_count == 1
    url = mock_open.call_args[0][0]
    assert "Copernicus_DSM_COG_10_N21_00_E081_00_DEM" in url


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_repeated_call_for_the_same_tile_does_not_reopen_it(mock_open):
    mock_open.return_value = _mock_dataset([100.0])

    fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)
    # A second dataset with different values proves the cache — not the
    # mock's own default_return_value — is what's actually being reused,
    # since a second real rasterio.open() call would use this.
    mock_open.return_value = _mock_dataset([999.0])
    result = fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)

    assert result == [100.0]  # served from the cached (first) dataset
    assert mock_open.call_count == 1


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_points_spanning_two_tiles_open_each_tile_once(mock_open):
    datasets = {
        "N21_00_E081_00": _mock_dataset([100.0]),
        "N22_00_E081_00": _mock_dataset([200.0]),
    }

    def dispatch(url, *args, **kwargs):
        for key, ds in datasets.items():
            if key in url:
                return ds
        raise AssertionError(f"unexpected tile url: {url}")

    mock_open.side_effect = dispatch

    result = fetch_from_copernicus_dem(
        [(21.9, 81.28), (22.1, 81.28)], deadline=time.monotonic() + 10
    )

    assert result == [100.0, 200.0]
    assert mock_open.call_count == 2


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_tile_open_failure_returns_none_and_trips_the_circuit(mock_open):
    mock_open.side_effect = Exception("network unreachable")

    result = fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)

    assert result == [None]
    assert circuit_breaker.is_open("copernicus-dem") is True


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_tripped_circuit_skips_without_calling_rasterio_open(mock_open):
    circuit_breaker.trip("copernicus-dem", cooldown_s=30.0)

    result = fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)

    assert result == [None]
    mock_open.assert_not_called()


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_disabled_skips_without_calling_rasterio_open(mock_open):
    original = settings.copernicus_dem_enabled
    settings.copernicus_dem_enabled = False
    try:
        result = fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)
        assert result == [None]
        mock_open.assert_not_called()
    finally:
        settings.copernicus_dem_enabled = original


@patch("app.providers.elevation.copernicus_dem.rasterio.open")
def test_sampling_exception_after_open_returns_none_for_that_tiles_points(mock_open):
    dataset = Mock()
    dataset.sample.side_effect = Exception("corrupt read")
    mock_open.return_value = dataset

    result = fetch_from_copernicus_dem([(21.26, 81.28)], deadline=time.monotonic() + 10)

    assert result == [None]

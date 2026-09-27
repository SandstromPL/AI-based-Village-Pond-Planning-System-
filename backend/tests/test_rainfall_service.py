"""Unit tests for Open-Meteo rainfall normalization and failure handling."""

from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.rainfall_service import (
    _normalize_open_meteo,
    clear_rainfall_cache,
    get_historical_rainfall,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_rainfall_cache()
    yield
    clear_rainfall_cache()


def test_normalize_open_meteo_calculates_multi_year_averages():
    result = _normalize_open_meteo({
        "daily": {
            "time": ["2023-06-01", "2023-07-01", "2024-06-01", "2024-07-01"],
            "precipitation_sum": [10.0, 30.0, 20.0, 40.0],
        }
    })

    assert result.status == "success"
    assert result.annual_avg_mm == 50.0
    assert result.monthly_avg_mm == {
        "Jan": 0.0, "Feb": 0.0, "Mar": 0.0, "Apr": 0.0,
        "May": 0.0, "Jun": 15.0, "Jul": 35.0, "Aug": 0.0,
        "Sep": 0.0, "Oct": 0.0, "Nov": 0.0, "Dec": 0.0,
    }
    assert result.seasonal_mm == {"monsoon_jun_sep_avg_mm": 50.0}


@patch("app.services.rainfall_service.httpx.get")
def test_historical_rainfall_returns_unavailable_on_rate_limit(mock_get):
    response = Mock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited",
        request=httpx.Request("GET", "https://example.test"),
        response=httpx.Response(429),
    )
    mock_get.return_value = response

    result = get_historical_rainfall(21.263169, 81.282811, 2024, 2024)

    assert result.status == "unavailable"
    assert "HTTP 429" in result.message


@patch("app.services.rainfall_service.httpx.get")
def test_historical_rainfall_requests_complete_years(mock_get):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "daily": {
            "time": ["2024-01-01", "2024-06-01"],
            "precipitation_sum": [1.0, 9.0],
        }
    }
    mock_get.return_value = response

    result = get_historical_rainfall(21.263169, 81.282811, 2024, 2024)

    assert result.status == "success"
    assert result.annual_avg_mm == 10.0
    assert mock_get.call_args.kwargs["params"] == {
        "latitude": 21.2632,
        "longitude": 81.2828,
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "daily": "precipitation_sum",
        "timezone": "auto",
    }

"""Historical rainfall retrieval and normalization using Open-Meteo.

The terrain pipeline must remain useful when the upstream weather provider is
unavailable. This module therefore converts provider/network failures into an
``unavailable`` rainfall result instead of propagating an exception.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from functools import lru_cache
import logging
from typing import Any

import httpx

from app.config import settings
from app.models.rainfall import NormalizedRainfallData
from app.utils.http_client import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

_MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def get_historical_rainfall(
    latitude: float,
    longitude: float,
    start_year: int | None = None,
    end_year: int | None = None,
) -> NormalizedRainfallData:
    """Return normalized multi-year daily-precipitation statistics.

    Coordinates are rounded before caching because an Open-Meteo grid cell
    covers a much larger area than the precision of a pond candidate point.
    The requested date window always contains complete calendar years.
    """
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return _unavailable("Rainfall data is unavailable: invalid location coordinates.")

    resolved_start_year = start_year or settings.rainfall_history_start_year
    resolved_end_year = (
        end_year
        or settings.rainfall_history_end_year
        or date.today().year - 1
    )
    if resolved_end_year < resolved_start_year:
        return _unavailable(
            "Rainfall data is unavailable: the historical end year precedes the start year."
        )

    return _get_cached_historical_rainfall(
        round(latitude, 4),
        round(longitude, 4),
        resolved_start_year,
        resolved_end_year,
    )


@lru_cache(maxsize=256)
def _get_cached_historical_rainfall(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
) -> NormalizedRainfallData:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "precipitation_sum",
        "timezone": "auto",
    }

    try:
        response = httpx.get(
            settings.open_meteo_archive_url,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=settings.rainfall_request_timeout_s,
        )
        response.raise_for_status()
        result = _normalize_open_meteo(response.json())
    except httpx.TimeoutException:
        logger.warning("Open-Meteo historical rainfall request timed out.")
        return _unavailable(
            "Rainfall data is temporarily unavailable: Open-Meteo request timed out. "
            "Terrain analysis was completed."
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.warning("Open-Meteo historical rainfall request failed with HTTP %s.", status_code)
        if status_code == 429:
            detail = "Open-Meteo rate limit reached (HTTP 429)"
        else:
            detail = f"Open-Meteo returned HTTP {status_code}"
        return _unavailable(
            f"Rainfall data is temporarily unavailable: {detail}. Terrain analysis was completed."
        )
    except httpx.HTTPError as exc:
        logger.warning("Open-Meteo historical rainfall request failed: %s", exc)
        return _unavailable(
            "Rainfall data is temporarily unavailable: unable to reach Open-Meteo. "
            "Terrain analysis was completed."
        )
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning("Open-Meteo returned unusable historical rainfall data: %s", exc)
        return _unavailable(
            "Rainfall data is temporarily unavailable: Open-Meteo returned invalid data. "
            "Terrain analysis was completed."
        )

    logger.info(
        "Retrieved Open-Meteo historical rainfall for %.4f, %.4f (%d-%d).",
        latitude,
        longitude,
        start_year,
        end_year,
    )
    return result


def _normalize_open_meteo(payload: dict[str, Any]) -> NormalizedRainfallData:
    """Normalize Open-Meteo daily precipitation into planning-ready averages."""
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ValueError("response has no daily precipitation data")

    dates = daily.get("time")
    precipitation = daily.get("precipitation_sum")
    if not isinstance(dates, list) or not isinstance(precipitation, list):
        raise ValueError("daily time or precipitation_sum is missing")
    if not dates or len(dates) != len(precipitation):
        raise ValueError("daily precipitation data is empty or misaligned")

    annual_totals: dict[int, float] = defaultdict(float)
    monthly_totals: dict[tuple[int, int], float] = defaultdict(float)
    for raw_date, raw_precipitation in zip(dates, precipitation):
        observed_date = date.fromisoformat(raw_date)
        rainfall_mm = float(raw_precipitation)
        if rainfall_mm < 0:
            raise ValueError("precipitation cannot be negative")
        annual_totals[observed_date.year] += rainfall_mm
        monthly_totals[(observed_date.year, observed_date.month)] += rainfall_mm

    if not annual_totals:
        raise ValueError("response contains no rainfall observations")

    annual_average = sum(annual_totals.values()) / len(annual_totals)
    monthly_average = {
        _MONTH_NAMES[month - 1]: round(
            sum(monthly_totals.get((year, month), 0.0) for year in annual_totals)
            / len(annual_totals),
            2,
        )
        for month in range(1, 13)
    }
    monsoon_average = sum(
        sum(monthly_totals.get((year, month), 0.0) for month in range(6, 10))
        for year in annual_totals
    ) / len(annual_totals)

    years = sorted(annual_totals)
    return NormalizedRainfallData(
        status="success",
        source="Open-Meteo Historical Weather API",
        annual_avg_mm=round(annual_average, 2),
        monthly_avg_mm=monthly_average,
        seasonal_mm={"monsoon_jun_sep_avg_mm": round(monsoon_average, 2)},
        message=(
            "Historical daily precipitation was averaged across complete calendar years "
            f"{years[0]}–{years[-1]}."
        ),
    )


def clear_rainfall_cache() -> None:
    """Clear cached provider results. Used by tests and operational maintenance."""
    _get_cached_historical_rainfall.cache_clear()


def _unavailable(message: str) -> NormalizedRainfallData:
    return NormalizedRainfallData(
        status="unavailable",
        source="Open-Meteo Historical Weather API",
        message=message,
    )

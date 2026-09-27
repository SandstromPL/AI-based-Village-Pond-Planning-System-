"""
Rainfall Service — Phase 2 Placeholder
========================================
# [EXTERNAL_API_PLACEHOLDER: Open-Meteo / IMD / NASA POWER]

In Phase 3, this service will:
  1. Accept a lat/lon from the recommended candidate location.
  2. Query the configured rainfall provider (Open-Meteo, IMD, or NASA POWER).
  3. Normalize the response into NormalizedRainfallData.
  4. Cache the result per analysis.

For Phase 2, it returns a placeholder object with clear messaging.
"""

from __future__ import annotations

import logging

from app.models.rainfall import NormalizedRainfallData

logger = logging.getLogger(__name__)


def get_historical_rainfall(
    latitude: float,
    longitude: float,
    start_year: int = 2015,
    end_year: int = 2024,
) -> NormalizedRainfallData:
    """
    Fetch historical rainfall for a location.

    # [EXTERNAL_API_PLACEHOLDER: Open-Meteo]
    Phase 3 implementation:
        url = f"{settings.open_meteo_base_url}/archive"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": f"{start_year}-01-01",
            "end_date": f"{end_year}-12-31",
            "daily": "precipitation_sum",
            "timezone": "auto",
        }
        response = httpx.get(url, params=params)
        return _normalize_open_meteo(response.json())

    Args:
        latitude, longitude: Location of the recommended candidate.
        start_year, end_year: Historical window.

    Returns:
        NormalizedRainfallData with placeholder status.
    """
    logger.warning(
        "Rainfall service is a placeholder. "
        "Configure an API provider in Phase 3. Location: (%.4f, %.4f)",
        latitude,
        longitude,
    )

    return NormalizedRainfallData(
        status="placeholder",
        source="EXTERNAL_API_PLACEHOLDER: Open-Meteo / IMD / NASA POWER",
        annual_avg_mm=None,
        monthly_avg_mm=None,
        seasonal_mm=None,
        message=(
            "Rainfall data not yet configured. "
            "Add your API provider key to .env and implement the provider in "
            "app/providers/rainfall/. See .env.example for available options."
        ),
    )

"""Planning-level annual runoff estimate for a delineated catchment."""

from __future__ import annotations

import logging

from app.config import settings
from app.models.rainfall import NormalizedRainfallData, RunoffResult

logger = logging.getLogger(__name__)


def estimate_runoff(
    rainfall: NormalizedRainfallData,
    catchment_area_km2: float,
    runoff_coefficient: float | None = None,
) -> RunoffResult:
    """Estimate annual collectable runoff volume in cubic metres.

    The estimate uses ``C × P × A`` where ``C`` is a dimensionless runoff
    coefficient, ``P`` is average annual rainfall in metres, and ``A`` is the
    catchment area in square metres. It is a planning estimate, not a flood
    design calculation.
    """
    if rainfall.status != "success" or rainfall.annual_avg_mm is None:
        return RunoffResult(
            message="Runoff is unavailable because historical rainfall data could not be retrieved."
        )
    if catchment_area_km2 <= 0:
        return RunoffResult(
            message="Runoff is unavailable because no valid catchment area was delineated."
        )

    coefficient = (
        settings.runoff_coefficient_default
        if runoff_coefficient is None
        else runoff_coefficient
    )
    if not 0 <= coefficient <= 1:
        return RunoffResult(
            message="Runoff is unavailable because the runoff coefficient must be between 0 and 1."
        )

    catchment_area_m2 = catchment_area_km2 * 1_000_000
    annual_rainfall_m = rainfall.annual_avg_mm / 1_000
    annual_runoff_m3 = coefficient * annual_rainfall_m * catchment_area_m2

    logger.info(
        "Estimated annual runoff: %.1f m³ (C=%.2f, rainfall=%.1f mm, area=%.4f km²).",
        annual_runoff_m3,
        coefficient,
        rainfall.annual_avg_mm,
        catchment_area_km2,
    )
    return RunoffResult(
        status="success",
        runoff_coefficient=coefficient,
        annual_runoff_m3=round(annual_runoff_m3, 2),
        message=(
            "Planning estimate using average historical rainfall, delineated catchment area, "
            f"and runoff coefficient C={coefficient:.2f}."
        ),
    )

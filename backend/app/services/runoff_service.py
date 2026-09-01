"""
Runoff Service — Phase 2 Placeholder
=======================================
# [EXTERNAL_API_PLACEHOLDER: Runoff coefficient needs soil/land-use data]

Phase 3 will implement the Rational Method:
    Q (m³/s) = C × i (mm/hr) × A (km²) × conversion_factor
    Annual runoff (m³) = C × annual_rainfall_m × catchment_area_m²

where:
    C = runoff coefficient (0.0–1.0), depends on soil type and land use
    i = rainfall intensity
    A = catchment area
"""

from __future__ import annotations

import logging

from app.models.rainfall import NormalizedRainfallData, RunoffResult

logger = logging.getLogger(__name__)


def estimate_runoff(
    rainfall: NormalizedRainfallData,
    catchment_area_km2: float,
    runoff_coefficient: float | None = None,
) -> RunoffResult:
    """
    Estimate annual runoff volume.

    # [EXTERNAL_API_PLACEHOLDER: runoff_coefficient needs soil/land-use data]

    Phase 3 implementation:
        if runoff_coefficient is None:
            # Fetch from soil/land-use API or use default for region
            runoff_coefficient = 0.35  # typical semi-arid agricultural land
        area_m2 = catchment_area_km2 * 1_000_000
        rainfall_m = rainfall.annual_avg_mm / 1000.0
        annual_runoff_m3 = runoff_coefficient * rainfall_m * area_m2
        return RunoffResult(status="success", runoff_coefficient=runoff_coefficient,
                            annual_runoff_m3=annual_runoff_m3)

    Args:
        rainfall:           Normalized rainfall data.
        catchment_area_km2: Delineated catchment area.
        runoff_coefficient: C value (optional override).

    Returns:
        RunoffResult with placeholder status.
    """
    logger.warning("Runoff service is a placeholder — rainfall data not yet available.")

    return RunoffResult(
        status="placeholder",
        runoff_coefficient=None,
        annual_runoff_m3=None,
        message=(
            "EXTERNAL_API_PLACEHOLDER: Runoff estimation requires rainfall data "
            "and soil/land-use information. Will be implemented in Phase 3."
        ),
    )

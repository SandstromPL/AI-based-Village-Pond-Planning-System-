"""
Pond Sizing Service — Phase 2 Placeholder
==========================================
# [EXTERNAL_API_PLACEHOLDER: Pond sizing needs runoff volume from rainfall API]

Phase 3 will implement:
    Given annual runoff volume → estimate pond depth, surface area, storage.

    Simple trapezoidal pond model:
        storage_volume = runoff_volume × retention_factor
        surface_area = storage_volume / avg_depth
        depth = configurable (typical village pond: 2–4 m)
"""

from __future__ import annotations

import logging

from app.models.rainfall import PondSizingResult, RunoffResult

logger = logging.getLogger(__name__)


def estimate_pond_size(
    runoff: RunoffResult,
    terrain_slope_deg: float | None = None,
) -> PondSizingResult:
    """
    Estimate planning-level pond dimensions from runoff volume.

    # [EXTERNAL_API_PLACEHOLDER: needs runoff volume from rainfall API]

    Phase 3 implementation:
        if runoff.annual_runoff_m3 is None:
            return PondSizingResult(status="placeholder", ...)
        retention_factor = 0.8  # retain 80% of annual runoff
        target_storage = runoff.annual_runoff_m3 * retention_factor
        depth = 3.0  # metres (typical village check dam / percolation pond)
        # Account for slope: shallower depth on steeper terrain
        if terrain_slope_deg and terrain_slope_deg > 5:
            depth = 2.0
        surface_area_m2 = target_storage / depth
        return PondSizingResult(
            status="success",
            recommended_depth_m=depth,
            estimated_surface_area_m2=surface_area_m2,
            estimated_storage_m3=target_storage,
        )

    Returns:
        PondSizingResult with placeholder status.
    """
    logger.warning("Pond sizing is a placeholder — runoff volume not yet available.")

    return PondSizingResult(
        status="placeholder",
        recommended_depth_m=None,
        estimated_surface_area_m2=None,
        estimated_storage_m3=None,
        message=(
            "EXTERNAL_API_PLACEHOLDER: Pond sizing requires runoff volume "
            "which depends on rainfall data. Will be implemented in Phase 3."
        ),
    )

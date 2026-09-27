"""Planning-level pond storage and dimension estimation."""

from __future__ import annotations

import logging

from app.config import settings
from app.models.rainfall import PondSizingResult, RunoffResult

logger = logging.getLogger(__name__)


def estimate_pond_size(
    runoff: RunoffResult,
    terrain_slope_deg: float | None = None,
) -> PondSizingResult:
    """Convert estimated annual runoff into an indicative pond storage design.

    Storage is the configured retention fraction of annual runoff. The surface
    area is a simple storage/depth calculation and must be field-validated
    before construction.
    """
    if runoff.status != "success" or runoff.annual_runoff_m3 is None:
        return PondSizingResult(
            message="Pond storage is unavailable because annual runoff could not be estimated."
        )

    depth_m = settings.pond_default_depth_m
    if (
        terrain_slope_deg is not None
        and terrain_slope_deg > settings.pond_steep_slope_threshold_deg
    ):
        depth_m = settings.pond_steep_slope_depth_m

    storage_m3 = runoff.annual_runoff_m3 * settings.pond_retention_factor
    surface_area_m2 = storage_m3 / depth_m

    logger.info(
        "Estimated pond storage: %.1f m³ at %.1f m depth (surface area %.1f m²).",
        storage_m3,
        depth_m,
        surface_area_m2,
    )
    return PondSizingResult(
        status="success",
        recommended_depth_m=round(depth_m, 2),
        estimated_surface_area_m2=round(surface_area_m2, 2),
        estimated_storage_m3=round(storage_m3, 2),
        message=(
            "Planning-level storage estimate using the configured retention factor "
            f"({settings.pond_retention_factor:.0%}) and indicative depth."
        ),
    )

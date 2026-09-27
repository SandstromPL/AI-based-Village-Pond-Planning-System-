"""
Land-use Constraint Service
=============================
Projects and buffers OSM exclusion geometries (buildings/roads/waterways/
water bodies/power lines) into a terrain's metric CRS and unions them into
a single geometry for fast candidate-point intersection checks.

Failure anywhere here (Overpass unreachable, or the filter disabled)
degrades to "no constraint filtering for this analysis" plus a warning —
never blocks the core terrain/catchment pipeline, matching the same
resilience pattern already used for rainfall and elevation.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from pyproj import Transformer
from shapely.ops import transform as shapely_transform, unary_union

from app.config import settings
from app.models.contour import BoundingBox
from app.providers.landuse.overpass import fetch_exclusion_geometries

logger = logging.getLogger(__name__)


def build_exclusion_union(
    bbox: BoundingBox,
    projected_crs: str,
) -> Tuple[Optional[object], List[str]]:
    """
    Fetch OSM exclusion geometries for bbox, project into projected_crs,
    buffer each category by its configured distance, and union into one
    geometry for cheap point-intersection checks.

    Returns (union_geometry_or_None, warnings). The union is None if the
    constraint filter is disabled or Overpass could not be reached — the
    caller treats that as "no filtering possible", not an error.
    """
    if not settings.landuse_constraint_enabled:
        return None, []

    layers = fetch_exclusion_geometries(bbox)
    if layers.status != "success":
        return None, [
            "Land-use constraint checking (buildings/roads/rivers) was skipped: "
            + layers.message
        ]

    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)

    buffered: List[object] = []
    buffered.extend(
        _project_and_buffer(layers.buildings, transformer, settings.landuse_building_buffer_m)
    )
    buffered.extend(
        _project_and_buffer(layers.roads, transformer, settings.landuse_road_buffer_m)
    )
    buffered.extend(
        _project_and_buffer(layers.waterways, transformer, settings.landuse_river_buffer_m)
    )
    buffered.extend(
        _project_and_buffer(layers.water_bodies, transformer, settings.landuse_river_buffer_m)
    )
    buffered.extend(
        _project_and_buffer(layers.power_lines, transformer, settings.landuse_powerline_buffer_m)
    )

    if not buffered:
        return None, []

    return unary_union(buffered), []


def _project_and_buffer(geometries, transformer: Transformer, buffer_m: float) -> List[object]:
    projected = []
    for geom in geometries:
        try:
            proj_geom = shapely_transform(transformer.transform, geom)
            projected.append(proj_geom.buffer(buffer_m))
        except Exception as exc:
            logger.debug("Skipping unprojectable land-use geometry: %s", exc)
    return projected

"""
Terrain Service
================
Orchestrates the DEM construction pipeline:
  1. Auto-detect UTM projection from contour centroid.
  2. Build the DEM grid via contour interpolation.
  3. Run Priority-Flood depression filling.
  4. Compute slope grid.
  5. Compute terrain statistics.
  6. Return a TerrainModel.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from app.algorithms.depression import fill_depressions
from app.algorithms.interpolation import interpolate_dem
from app.algorithms.slope import compute_slope
from app.config import settings
from app.models.contour import NormalizedContourData
from app.models.terrain import TerrainModel, TerrainStatistics
from app.utils.geo import utm_epsg_from_lonlat

logger = logging.getLogger(__name__)


def build_terrain_model(contour_data: NormalizedContourData) -> TerrainModel:
    """
    Build a full terrain model from normalised contour data.

    Args:
        contour_data: Parsed contours in EPSG:4326.

    Returns:
        TerrainModel with dem, slope, filled_dem, statistics, and grid metadata.
    """
    from pyproj import Transformer

    bbox = contour_data.bbox
    resolution_m = settings.dem_resolution_m
    pad = settings.dem_bbox_padding_frac
    method = settings.dem_interp_method

    # ── Auto-detect UTM CRS ───────────────────────────────────────────────
    projected_crs = utm_epsg_from_lonlat(bbox.center_lon, bbox.center_lat)
    logger.info("Using projected CRS: %s", projected_crs)

    # ── Project the bounding box to UTM ──────────────────────────────────
    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)

    min_x, min_y = transformer.transform(bbox.min_lon, bbox.min_lat)
    max_x, max_y = transformer.transform(bbox.max_lon, bbox.max_lat)

    # Add padding
    x_pad = (max_x - min_x) * pad
    y_pad = (max_y - min_y) * pad
    padded_min_x = min_x - x_pad
    padded_max_x = max_x + x_pad
    padded_min_y = min_y - y_pad
    padded_max_y = max_y + y_pad

    # Grid dimensions
    grid_cols = max(10, math.ceil((padded_max_x - padded_min_x) / resolution_m))
    grid_rows = max(10, math.ceil((padded_max_y - padded_min_y) / resolution_m))

    # Origin = top-left corner (x_min, y_max)
    origin_x = padded_min_x
    origin_y = padded_max_y

    logger.info(
        "DEM grid: %dx%d cells at %.0f m resolution (%.1f × %.1f km).",
        grid_rows,
        grid_cols,
        resolution_m,
        grid_cols * resolution_m / 1000,
        grid_rows * resolution_m / 1000,
    )

    # ── Build raw DEM ─────────────────────────────────────────────────────
    dem = interpolate_dem(
        contour_data=contour_data,
        origin_x=origin_x,
        origin_y=origin_y,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        resolution_m=resolution_m,
        projected_crs=projected_crs,
        method=method,
    )

    # ── Depression filling ────────────────────────────────────────────────
    filled_dem = fill_depressions(dem)

    # ── Slope ─────────────────────────────────────────────────────────────
    slope = compute_slope(filled_dem, resolution_m)

    # ── Statistics ───────────────────────────────────────────────────────
    valid_elev = dem[~np.isnan(dem)]
    valid_slope = slope[~np.isnan(slope)]

    stats = TerrainStatistics(
        min_elevation_m=float(valid_elev.min()),
        max_elevation_m=float(valid_elev.max()),
        mean_elevation_m=float(valid_elev.mean()),
        elevation_range_m=float(valid_elev.max() - valid_elev.min()),
        avg_slope_deg=float(valid_slope.mean()),
        max_slope_deg=float(valid_slope.max()),
        dem_resolution_m=resolution_m,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
    )

    logger.info(
        "Terrain stats: elev=[%.1f, %.1f] m, avg slope=%.1f°.",
        stats.min_elevation_m,
        stats.max_elevation_m,
        stats.avg_slope_deg,
    )

    return TerrainModel(
        dem=dem,
        slope=slope,
        filled_dem=filled_dem,
        stats=stats,
        origin_x=origin_x,
        origin_y=origin_y,
        resolution_m=resolution_m,
        projected_crs=projected_crs,
        source_crs="EPSG:4326",
    )

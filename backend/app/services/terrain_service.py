"""
Terrain Service
================
Two ways to build a TerrainModel, sharing the same downstream pipeline:

  1. build_terrain_model(contour_data)
     Contour-upload path — DEM built by interpolating uploaded contour lines.

  2. build_terrain_model_from_area(polygon_coords, resolution_m)
     Map-selected-area path — DEM built from real point elevations fetched
     from Open-Elevation for a grid sampled over the user-drawn polygon's
     bounding box (no contour file involved).

Both then run the same tail: Priority-Flood depression filling, slope
computation, and terrain statistics.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy.interpolate import griddata

from app.algorithms.depression import fill_depressions
from app.algorithms.interpolation import interpolate_dem
from app.algorithms.slope import compute_slope
from app.config import settings
from app.models.contour import BoundingBox, NormalizedContourData
from app.models.terrain import TerrainModel, TerrainStatistics
from app.providers.elevation.open_elevation import fetch_elevations
from app.utils.geo import (
    approx_bbox_area_km2,
    bbox_from_polygon,
    projected_to_lonlat,
    utm_epsg_from_lonlat,
)

logger = logging.getLogger(__name__)


class AreaTooLargeError(ValueError):
    """Raised when a selected area exceeds the configured size limit."""


class ElevationUnavailableError(RuntimeError):
    """Raised when too few elevation points could be fetched to build a DEM."""


@dataclass
class _GridSpec:
    origin_x: float
    origin_y: float
    grid_rows: int
    grid_cols: int
    resolution_m: float


def _compute_grid_spec(
    bbox: BoundingBox,
    projected_crs: str,
    resolution_m: float,
    pad: float,
) -> _GridSpec:
    """Compute DEM grid dimensions/origin for a WGS84 bbox in a projected CRS."""
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)

    min_x, min_y = transformer.transform(bbox.min_lon, bbox.min_lat)
    max_x, max_y = transformer.transform(bbox.max_lon, bbox.max_lat)

    x_pad = (max_x - min_x) * pad
    y_pad = (max_y - min_y) * pad
    padded_min_x = min_x - x_pad
    padded_max_x = max_x + x_pad
    padded_min_y = min_y - y_pad
    padded_max_y = max_y + y_pad

    grid_cols = max(10, math.ceil((padded_max_x - padded_min_x) / resolution_m))
    grid_rows = max(10, math.ceil((padded_max_y - padded_min_y) / resolution_m))

    return _GridSpec(
        origin_x=padded_min_x,
        origin_y=padded_max_y,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        resolution_m=resolution_m,
    )


def _grid_cell_centers_projected(spec: _GridSpec) -> Tuple[np.ndarray, np.ndarray]:
    """Return (gx, gy) 2D arrays of projected cell-centre coordinates, shape (rows, cols)."""
    col_indices = np.arange(spec.grid_cols)
    row_indices = np.arange(spec.grid_rows)
    grid_x = spec.origin_x + (col_indices + 0.5) * spec.resolution_m
    grid_y = spec.origin_y - (row_indices + 0.5) * spec.resolution_m  # y decreases downward
    gx, gy = np.meshgrid(grid_x, grid_y)
    return gx, gy


def _finish_terrain_model(
    dem: np.ndarray,
    spec: _GridSpec,
    projected_crs: str,
) -> TerrainModel:
    """Shared tail: depression fill, slope, statistics, TerrainModel assembly."""
    filled_dem = fill_depressions(dem)
    slope = compute_slope(filled_dem, spec.resolution_m)

    valid_elev = dem[~np.isnan(dem)]
    valid_slope = slope[~np.isnan(slope)]

    stats = TerrainStatistics(
        min_elevation_m=float(valid_elev.min()),
        max_elevation_m=float(valid_elev.max()),
        mean_elevation_m=float(valid_elev.mean()),
        elevation_range_m=float(valid_elev.max() - valid_elev.min()),
        avg_slope_deg=float(valid_slope.mean()),
        max_slope_deg=float(valid_slope.max()),
        dem_resolution_m=spec.resolution_m,
        grid_rows=spec.grid_rows,
        grid_cols=spec.grid_cols,
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
        origin_x=spec.origin_x,
        origin_y=spec.origin_y,
        resolution_m=spec.resolution_m,
        projected_crs=projected_crs,
        source_crs="EPSG:4326",
    )


def build_terrain_model(contour_data: NormalizedContourData) -> TerrainModel:
    """
    Build a full terrain model from normalised contour data.

    Args:
        contour_data: Parsed contours in EPSG:4326.

    Returns:
        TerrainModel with dem, slope, filled_dem, statistics, and grid metadata.
    """
    bbox = contour_data.bbox
    resolution_m = settings.dem_resolution_m
    pad = settings.dem_bbox_padding_frac
    method = settings.dem_interp_method

    projected_crs = utm_epsg_from_lonlat(bbox.center_lon, bbox.center_lat)
    logger.info("Using projected CRS: %s", projected_crs)

    spec = _compute_grid_spec(bbox, projected_crs, resolution_m, pad)

    logger.info(
        "DEM grid: %dx%d cells at %.0f m resolution (%.1f × %.1f km).",
        spec.grid_rows,
        spec.grid_cols,
        resolution_m,
        spec.grid_cols * resolution_m / 1000,
        spec.grid_rows * resolution_m / 1000,
    )

    dem = interpolate_dem(
        contour_data=contour_data,
        origin_x=spec.origin_x,
        origin_y=spec.origin_y,
        grid_rows=spec.grid_rows,
        grid_cols=spec.grid_cols,
        resolution_m=resolution_m,
        projected_crs=projected_crs,
        method=method,
    )

    return _finish_terrain_model(dem, spec, projected_crs)


def build_terrain_model_from_area(
    polygon_coords: List[Tuple[float, float]],
    resolution_m: Optional[float] = None,
) -> Tuple[TerrainModel, List[str]]:
    """
    Build a terrain model for a user-drawn map area, with no contour file.

    Elevations are fetched from Open-Elevation for a grid sampled over the
    polygon's bounding box. Returns (terrain_model, warnings).

    Raises:
        AreaTooLargeError: the polygon's bbox exceeds settings.selected_area_max_km2.
        ElevationUnavailableError: too few elevation points could be retrieved
            to build a usable DEM.
    """
    warnings: List[str] = []
    bbox = bbox_from_polygon(polygon_coords)

    area_km2 = approx_bbox_area_km2(bbox)
    if area_km2 > settings.selected_area_max_km2:
        raise AreaTooLargeError(
            f"Selected area (~{area_km2:.1f} km²) exceeds the maximum allowed "
            f"({settings.selected_area_max_km2:.1f} km²). Please draw a smaller area."
        )

    projected_crs = utm_epsg_from_lonlat(bbox.center_lon, bbox.center_lat)
    logger.info("Using projected CRS: %s", projected_crs)

    effective_resolution_m = resolution_m or settings.dem_resolution_m
    pad = settings.dem_bbox_padding_frac
    spec = _compute_grid_spec(bbox, projected_crs, effective_resolution_m, pad)

    total_points = spec.grid_rows * spec.grid_cols
    if total_points > settings.selected_area_max_grid_points:
        scale_factor = math.sqrt(total_points / settings.selected_area_max_grid_points)
        coarsened_resolution_m = effective_resolution_m * scale_factor
        spec = _compute_grid_spec(bbox, projected_crs, coarsened_resolution_m, pad)
        warnings.append(
            f"Selected area required coarsening DEM resolution from "
            f"{effective_resolution_m:.0f} m to {spec.resolution_m:.0f} m to bound "
            f"elevation API usage ({total_points} → {spec.grid_rows * spec.grid_cols} cells)."
        )

    logger.info(
        "Area DEM grid: %dx%d cells at %.0f m resolution.",
        spec.grid_rows,
        spec.grid_cols,
        spec.resolution_m,
    )

    gx, gy = _grid_cell_centers_projected(spec)
    lons, lats = projected_to_lonlat(gx.ravel(), gy.ravel(), projected_crs)

    elevations = fetch_elevations(list(zip(lats.tolist(), lons.tolist())))
    elevations_arr = np.array(
        [e if e is not None else np.nan for e in elevations], dtype=np.float64
    )

    n_missing = int(np.isnan(elevations_arr).sum())
    n_total = elevations_arr.size
    if n_missing > 0.5 * n_total:
        raise ElevationUnavailableError(
            f"Elevation data unavailable for {n_missing}/{n_total} grid cells. "
            "The elevation provider may be down; try again shortly or draw a smaller area."
        )

    if n_missing > 0:
        known_mask = ~np.isnan(elevations_arr)
        target_points = np.column_stack([gx.ravel(), gy.ravel()])
        known_points = target_points[known_mask]
        known_values = elevations_arr[known_mask]
        filled = griddata(known_points, known_values, target_points, method="nearest")
        elevations_arr[~known_mask] = filled[~known_mask]
        warnings.append(
            f"{n_missing} of {n_total} elevation samples were unavailable and were "
            "filled using nearest-neighbour interpolation."
        )

    dem = elevations_arr.reshape(spec.grid_rows, spec.grid_cols)
    logger.info(
        "Area DEM built: shape=%s, elevation=[%.1f, %.1f] m.",
        dem.shape,
        float(np.nanmin(dem)),
        float(np.nanmax(dem)),
    )

    terrain = _finish_terrain_model(dem, spec, projected_crs)
    return terrain, warnings

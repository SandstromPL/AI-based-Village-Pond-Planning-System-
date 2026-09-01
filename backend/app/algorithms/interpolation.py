"""
Contour-to-DEM Interpolation
==============================
Converts a set of contour lines (elevation + geometry) into a regular
DEM (Digital Elevation Model) grid using spatial interpolation.

Process:
  1. Project all contour coordinates from WGS84 to UTM (metric).
  2. Sample points at a fixed interval along each contour line.
  3. Use scipy.interpolate.griddata to interpolate a regular grid.
     - First pass: 'linear' (fast, good for most areas)
     - Second pass: 'nearest' to fill any NaN edge cells
  4. Return a numpy 2D array with the elevation grid.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
from scipy.interpolate import griddata

from app.models.contour import NormalizedContourData

logger = logging.getLogger(__name__)

# Sample contour points every N metres along each line
_CONTOUR_SAMPLE_INTERVAL_M = 10.0


def interpolate_dem(
    contour_data: NormalizedContourData,
    origin_x: float,
    origin_y: float,
    grid_rows: int,
    grid_cols: int,
    resolution_m: float,
    projected_crs: str,
    method: str = "linear",
) -> np.ndarray:
    """
    Build a DEM grid from contour data using scipy griddata interpolation.

    Args:
        contour_data:  Normalized contour lines (WGS84).
        origin_x/y:    Top-left corner of the grid in projected CRS.
        grid_rows/cols: Dimensions of the output grid.
        resolution_m:  Cell size in metres.
        projected_crs: UTM EPSG code for metric calculations.
        method:        Interpolation method ('linear', 'cubic', 'nearest').

    Returns:
        dem: float64 2D array, shape (grid_rows, grid_cols).
             NaN for cells outside the convex hull of contour data.
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", projected_crs, always_xy=True)

    # ── Sample points from all contours ──────────────────────────────────
    sample_xs: List[float] = []
    sample_ys: List[float] = []
    sample_zs: List[float] = []

    for contour in contour_data.contours:
        coords = contour.coordinates
        if len(coords) < 2:
            continue

        # Project contour coordinates to UTM
        lons = np.array([c[0] for c in coords])
        lats = np.array([c[1] for c in coords])
        xs, ys = transformer.transform(lons, lats)

        # Sample along each segment at fixed intervals
        for i in range(len(xs) - 1):
            dx = xs[i + 1] - xs[i]
            dy = ys[i + 1] - ys[i]
            seg_len = np.sqrt(dx**2 + dy**2)

            if seg_len == 0:
                continue

            n_samples = max(2, int(seg_len / _CONTOUR_SAMPLE_INTERVAL_M))
            t_vals = np.linspace(0, 1, n_samples)
            sample_xs.extend(xs[i] + t_vals * dx)
            sample_ys.extend(ys[i] + t_vals * dy)
            sample_zs.extend([contour.elevation_m] * n_samples)

    if len(sample_xs) < 4:
        raise ValueError(
            "Insufficient contour sample points for interpolation "
            f"(got {len(sample_xs)}, need at least 4)."
        )

    points = np.column_stack([sample_xs, sample_ys])
    values = np.array(sample_zs)

    logger.debug(
        "Interpolating DEM from %d sample points onto a %dx%d grid (method=%s).",
        len(sample_xs),
        grid_rows,
        grid_cols,
        method,
    )

    # ── Build target grid ─────────────────────────────────────────────────
    # Grid cell centres in projected coordinates
    col_indices = np.arange(grid_cols)
    row_indices = np.arange(grid_rows)
    grid_x = origin_x + (col_indices + 0.5) * resolution_m
    grid_y = origin_y - (row_indices + 0.5) * resolution_m  # y decreases downward
    gx, gy = np.meshgrid(grid_x, grid_y)
    grid_points = np.column_stack([gx.ravel(), gy.ravel()])

    # ── Interpolate ───────────────────────────────────────────────────────
    dem_flat = griddata(points, values, grid_points, method=method)

    # Fill NaN holes with nearest-neighbour
    nan_mask = np.isnan(dem_flat)
    if nan_mask.any():
        dem_flat_nearest = griddata(points, values, grid_points, method="nearest")
        dem_flat[nan_mask] = dem_flat_nearest[nan_mask]
        logger.debug("Filled %d NaN DEM cells with nearest-neighbour fallback.", int(nan_mask.sum()))

    dem = dem_flat.reshape(grid_rows, grid_cols)

    logger.info(
        "DEM built: shape=%s, elevation=[%.1f, %.1f] m.",
        dem.shape,
        float(np.nanmin(dem)),
        float(np.nanmax(dem)),
    )

    return dem.astype(np.float64)

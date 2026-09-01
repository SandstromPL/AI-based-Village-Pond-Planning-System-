"""
Slope Calculation
==================
Compute slope in degrees from a DEM using finite-difference gradient.

    slope = arctan(sqrt((dz/dx)² + (dz/dy)²))

where dz/dx and dz/dy are the elevation gradient in the x and y directions
computed using central differences (forward/backward at edges).
"""

from __future__ import annotations
import numpy as np


def compute_slope(dem: np.ndarray, resolution_m: float) -> np.ndarray:
    """
    Compute slope in degrees for every cell of a DEM.

    Args:
        dem:          2D float64 elevation array (metres).
        resolution_m: Cell size in metres.

    Returns:
        slope: 2D float64 array, same shape as dem, in degrees (0–90).
               NaN cells in dem produce NaN slope.
    """
    # numpy gradient uses central differences internally
    # Returns (dz/dy, dz/dx) — note axis order (row=y, col=x)
    dz_dy, dz_dx = np.gradient(dem, resolution_m, resolution_m)

    magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_rad = np.arctan(magnitude)
    slope_deg = np.degrees(slope_rad)

    return slope_deg.astype(np.float64)

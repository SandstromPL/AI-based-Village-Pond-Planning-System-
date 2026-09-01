"""
Pydantic models for the terrain representation (DEM, slope, statistics).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple
import numpy as np


@dataclass
class TerrainStatistics:
    min_elevation_m: float
    max_elevation_m: float
    mean_elevation_m: float
    elevation_range_m: float
    avg_slope_deg: float
    max_slope_deg: float
    dem_resolution_m: float
    grid_rows: int
    grid_cols: int


@dataclass
class TerrainModel:
    """
    The DEM-like raster representation of the terrain built from contour lines.
    All grids are 2D numpy arrays in the projected CRS (UTM).

    origin_x, origin_y: top-left corner in projected coordinates (metres).
    resolution_m: cell size in metres.
    projected_crs: e.g. "EPSG:32644" (UTM zone auto-detected from contour centroid).
    source_crs: always "EPSG:4326" (WGS84 geographic input).
    """

    dem: np.ndarray           # elevation in metres, shape (rows, cols)
    slope: np.ndarray         # slope in degrees, shape (rows, cols)
    filled_dem: np.ndarray    # hydrologically conditioned DEM (post depression-fill)
    stats: TerrainStatistics

    origin_x: float           # projected CRS x coordinate of top-left corner
    origin_y: float           # projected CRS y coordinate of top-left corner
    resolution_m: float
    projected_crs: str
    source_crs: str = "EPSG:4326"

    @property
    def shape(self) -> Tuple[int, int]:
        return self.dem.shape

    def cell_to_projected(self, row: int, col: int) -> Tuple[float, float]:
        """Convert grid indices to projected (x, y) coordinates (cell centre)."""
        x = self.origin_x + (col + 0.5) * self.resolution_m
        y = self.origin_y - (row + 0.5) * self.resolution_m
        return x, y

    def projected_to_cell(self, x: float, y: float) -> Tuple[int, int]:
        """Convert projected coordinates to nearest grid cell indices."""
        col = int((x - self.origin_x) / self.resolution_m)
        row = int((self.origin_y - y) / self.resolution_m)
        return row, col

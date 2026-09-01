"""
Pydantic models for flow direction, flow accumulation, and catchment results.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import numpy as np


@dataclass
class FlowData:
    """
    Hydrological flow grids computed from the terrain model.

    flow_direction: 2D array, values 0-7 (D8: N,NE,E,SE,S,SW,W,NW) or -1 for no-data.
    flow_accumulation: 2D array, upstream contributing cell count per cell.
    """

    flow_direction: np.ndarray   # shape (rows, cols), int8
    flow_accumulation: np.ndarray  # shape (rows, cols), int32


@dataclass
class CatchmentResult:
    """
    Delineated catchment for a single pour point (candidate location).
    """

    pour_point_row: int
    pour_point_col: int
    area_km2: float
    cell_count: int
    mask: np.ndarray                        # bool array, shape (rows, cols)
    boundary_geojson: Dict[str, Any]        # GeoJSON Polygon in EPSG:4326
    drainage_lines_geojson: Optional[Dict[str, Any]] = None  # GeoJSON LineString(s)

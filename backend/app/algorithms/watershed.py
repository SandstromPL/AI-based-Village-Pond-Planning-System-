"""
Catchment (Watershed) Delineation Algorithm
============================================
Given a pour point (pond candidate cell) and the D8 flow direction grid,
delineate the catchment by tracing upstream via BFS.

The flow direction grid defines a directed graph:
    cell → its downstream neighbour

The reverse graph gives:
    cell → all cells that drain INTO it (upstream neighbours)

A BFS/DFS from the pour point over the reverse graph collects every cell
that eventually drains to the pour point. That set of cells is the catchment.

The catchment mask is then vectorised to a GeoJSON Polygon and the area
is calculated from the cell count × cell area.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Dict, Any, Tuple

import numpy as np

from app.algorithms.flow_direction import D8_OFFSETS
from app.models.catchment import CatchmentResult
from app.utils.geo import cell_area_m2
from app.utils.geojson import mask_to_geojson_polygon

logger = logging.getLogger(__name__)


def build_reverse_flow(flow_direction: np.ndarray) -> Dict[Tuple[int, int], list]:
    """
    Build a reverse flow-direction mapping: cell → list of upstream cells.

    For each cell C with direction d pointing to downstream cell D:
        reverse_map[D].append(C)
    """
    rows, cols = flow_direction.shape
    reverse_map: Dict[Tuple[int, int], list] = {}

    for r in range(rows):
        for c in range(cols):
            d = int(flow_direction[r, c])
            if d < 0:
                continue
            dr, dc = D8_OFFSETS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                key = (nr, nc)
                if key not in reverse_map:
                    reverse_map[key] = []
                reverse_map[key].append((r, c))

    return reverse_map


def delineate_catchment(
    pour_point_row: int,
    pour_point_col: int,
    flow_direction: np.ndarray,
    resolution_m: float,
    origin_x: float,
    origin_y: float,
    projected_crs: str,
) -> CatchmentResult:
    """
    Delineate the catchment for a pour point using upstream BFS.

    Args:
        pour_point_row, pour_point_col: Grid indices of the candidate location.
        flow_direction: D8 flow direction grid.
        resolution_m:   DEM cell size in metres.
        origin_x/y:     Top-left corner of the grid in projected coordinates.
        projected_crs:  The projected CRS (e.g. "EPSG:32644").

    Returns:
        CatchmentResult with mask, area, and GeoJSON boundary polygon.
    """
    rows, cols = flow_direction.shape
    reverse_map = build_reverse_flow(flow_direction)

    # BFS upstream from pour point
    visited = set()
    queue = deque()
    queue.append((pour_point_row, pour_point_col))
    visited.add((pour_point_row, pour_point_col))

    while queue:
        r, c = queue.popleft()
        for ur, uc in reverse_map.get((r, c), []):
            if (ur, uc) not in visited:
                visited.add((ur, uc))
                queue.append((ur, uc))

    # Build boolean mask
    mask = np.zeros((rows, cols), dtype=bool)
    for r, c in visited:
        mask[r, c] = True

    cell_count = int(mask.sum())
    area_m2 = cell_count * cell_area_m2(resolution_m)
    area_km2 = area_m2 / 1_000_000.0

    # Vectorise mask to GeoJSON polygon (reprojected to WGS84)
    boundary_geojson = mask_to_geojson_polygon(
        mask=mask,
        origin_x=origin_x,
        origin_y=origin_y,
        resolution_m=resolution_m,
        projected_crs=projected_crs,
    )

    logger.debug(
        "Catchment at (%d, %d): %d cells, %.4f km².",
        pour_point_row,
        pour_point_col,
        cell_count,
        area_km2,
    )

    return CatchmentResult(
        pour_point_row=pour_point_row,
        pour_point_col=pour_point_col,
        area_km2=area_km2,
        cell_count=cell_count,
        mask=mask,
        boundary_geojson=boundary_geojson,
    )

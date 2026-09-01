"""
Catchment Service
==================
Computes flow direction, flow accumulation, and delineates catchments
for candidate locations.
"""

from __future__ import annotations

import logging

from app.algorithms.flow_accumulation import compute_flow_accumulation
from app.algorithms.flow_direction import compute_flow_direction
from app.algorithms.watershed import delineate_catchment
from app.models.catchment import CatchmentResult, FlowData
from app.models.terrain import TerrainModel

logger = logging.getLogger(__name__)


def compute_flow_data(terrain: TerrainModel) -> FlowData:
    """
    Compute D8 flow direction and flow accumulation for a terrain model.

    Args:
        terrain: Built TerrainModel with filled_dem.

    Returns:
        FlowData with flow_direction and flow_accumulation grids.
    """
    logger.info("Computing D8 flow direction...")
    flow_dir = compute_flow_direction(terrain.filled_dem, terrain.resolution_m)

    logger.info("Computing flow accumulation...")
    flow_acc = compute_flow_accumulation(flow_dir)

    return FlowData(
        flow_direction=flow_dir,
        flow_accumulation=flow_acc,
    )


def get_catchment(
    row: int,
    col: int,
    terrain: TerrainModel,
    flow_data: FlowData,
) -> CatchmentResult:
    """
    Delineate the catchment for a single pour point.

    Args:
        row, col:   Grid cell indices of the pour point.
        terrain:    TerrainModel (for grid metadata).
        flow_data:  Precomputed flow direction grid.

    Returns:
        CatchmentResult with area, cell count, mask, and GeoJSON boundary.
    """
    return delineate_catchment(
        pour_point_row=row,
        pour_point_col=col,
        flow_direction=flow_data.flow_direction,
        resolution_m=terrain.resolution_m,
        origin_x=terrain.origin_x,
        origin_y=terrain.origin_y,
        projected_crs=terrain.projected_crs,
    )

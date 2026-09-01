"""
Priority-Flood Depression Filling Algorithm
============================================
Reference: Barnes et al. (2014) "Priority-Flood: An Optimal Depression-Filling
           and Watershed-Labeling Algorithm for Digital Elevation Models."
           Computers & Geosciences, 62, 117–127.

Purpose:
  Raw DEMs (especially those interpolated from contour lines) often contain
  artificial sinks — cells from which water has no downhill path due to
  interpolation artifacts. The Priority-Flood algorithm raises all sunk cells
  to the elevation of their lowest outlet so that every cell has a valid
  downhill flow path.

Algorithm:
  1. Push all boundary cells (edges) into a min-heap priority queue.
  2. Pop the lowest-priority cell C from the queue.
  3. For each unprocessed neighbour N of C:
       - If N's elevation < C's elevation, raise N to C's elevation (fill).
       - Mark N as processed.
       - Push N into the priority queue.
  4. Repeat until the queue is empty.

Result: a hydrologically conditioned DEM where every cell has at least one
        downhill path to the boundary.
"""

from __future__ import annotations

import heapq
import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# D8 neighbour offsets (dr, dc) — 8-connected
_NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1),
               ( 0, -1),           ( 0, 1),
               ( 1, -1), ( 1, 0), ( 1, 1)]

_NODATA = np.nan


def fill_depressions(dem: np.ndarray) -> np.ndarray:
    """
    Apply Priority-Flood depression filling to a DEM.

    Args:
        dem: 2D float array of elevations. NaN cells are treated as no-data
             and are not filled (they act as open boundaries).

    Returns:
        filled_dem: 2D float array, same shape as dem, with all depressions
                    raised to their spill elevation. NaN cells unchanged.
    """
    rows, cols = dem.shape
    filled = dem.copy().astype(np.float64)
    closed = np.zeros((rows, cols), dtype=bool)

    # Min-heap: (elevation, row, col)
    heap: List[Tuple[float, int, int]] = []

    # Seed the heap with all boundary cells and NaN neighbours of valid cells
    for r in range(rows):
        for c in range(cols):
            if np.isnan(filled[r, c]):
                closed[r, c] = True  # treat NaN as already processed
                continue
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                heapq.heappush(heap, (filled[r, c], r, c))
                closed[r, c] = True

    cells_filled = 0

    while heap:
        elev, r, c = heapq.heappop(heap)

        for dr, dc in _NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if closed[nr, nc]:
                continue
            if np.isnan(filled[nr, nc]):
                closed[nr, nc] = True
                continue

            # Fill if the neighbour is lower than current cell
            if filled[nr, nc] < filled[r, c]:
                filled[nr, nc] = filled[r, c]
                cells_filled += 1

            closed[nr, nc] = True
            heapq.heappush(heap, (filled[nr, nc], nr, nc))

    if cells_filled:
        logger.debug("Depression filling raised %d cells.", cells_filled)

    return filled

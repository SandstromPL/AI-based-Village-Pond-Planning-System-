"""
D8 Flow Direction Algorithm
============================
For each grid cell, the steepest downhill neighbour (out of 8 neighbours)
determines the flow direction.

Direction encoding (matches ESRI / standard GIS convention):
    NW=7  N=0  NE=1
     W=6   X    E=2
    SW=5  S=4  SE=3

    Stored as int8. -1 = no data / flat / boundary with no outlet.

Diagonal distance is scaled by √2 to give correct gradient per unit distance.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)

# D8 direction index → (row_delta, col_delta)
D8_OFFSETS: dict[int, Tuple[int, int]] = {
    0: (-1,  0),   # N
    1: (-1,  1),   # NE
    2: ( 0,  1),   # E
    3: ( 1,  1),   # SE
    4: ( 1,  0),   # S
    5: ( 1, -1),   # SW
    6: ( 0, -1),   # W
    7: (-1, -1),   # NW
}

# Distance multipliers for diagonal vs. cardinal neighbours
_SQRT2 = np.sqrt(2.0)
_DIST_MULT = {
    0: 1.0, 1: _SQRT2, 2: 1.0, 3: _SQRT2,
    4: 1.0, 5: _SQRT2, 6: 1.0, 7: _SQRT2,
}

_NODATA_DIR = np.int8(-1)


def compute_flow_direction(filled_dem: np.ndarray, resolution_m: float = 1.0) -> np.ndarray:
    """
    Compute the D8 flow direction grid from a hydrologically conditioned DEM.

    Args:
        filled_dem:   2D float64 array (depression-filled). NaN = no-data.
        resolution_m: Cell size in metres (used to normalise gradient for diagonals).

    Returns:
        flow_dir: int8 2D array, same shape as filled_dem.
                  Values 0-7 = D8 direction, -1 = no flow (boundary/flat/NaN).
    """
    rows, cols = filled_dem.shape
    flow_dir = np.full((rows, cols), _NODATA_DIR, dtype=np.int8)

    for r in range(rows):
        for c in range(cols):
            if np.isnan(filled_dem[r, c]):
                continue

            best_dir = _NODATA_DIR
            best_gradient = 0.0  # steepest downhill gradient seen

            for d, (dr, dc) in D8_OFFSETS.items():
                nr, nc = r + dr, c + dc
                if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                    continue
                if np.isnan(filled_dem[nr, nc]):
                    continue

                drop = filled_dem[r, c] - filled_dem[nr, nc]
                if drop <= 0:
                    continue

                # Gradient = elevation drop / horizontal distance
                dist = resolution_m * _DIST_MULT[d]
                gradient = drop / dist

                if gradient > best_gradient:
                    best_gradient = gradient
                    best_dir = np.int8(d)

            flow_dir[r, c] = best_dir

    flat_count = int(np.sum(flow_dir == _NODATA_DIR) - np.sum(np.isnan(filled_dem)))
    if flat_count > 0:
        logger.debug("%d flat/undrained cells detected after D8 computation.", flat_count)

    return flow_dir


def direction_to_offset(direction: int) -> Tuple[int, int]:
    """Return the (row_delta, col_delta) for a given D8 direction index."""
    return D8_OFFSETS[direction]

"""
Flow Accumulation Algorithm
=============================
Computes the number of upstream cells that drain into each cell,
using a topological sort over the D8 flow-direction graph.

High flow accumulation values mark drainage convergence points —
ideal seeds for pond candidate generation.

Algorithm:
  1. Compute in-degree: for each cell, count how many of its neighbours
     drain INTO it (based on the flow direction of those neighbours).
  2. Initialise a queue with all cells that have in-degree = 0
     (headwater cells — no cells flow into them).
  3. Process cells in topological order:
       - When a cell C is dequeued, propagate its accumulated count
         to its downstream cell D:
           acc[D] += acc[C] + 1
       - Decrement in-degree of D. If in-degree reaches 0, enqueue D.

This is a standard topological sort (Kahn's algorithm) adapted for
the flow-direction DAG.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

from app.algorithms.flow_direction import D8_OFFSETS

logger = logging.getLogger(__name__)


def compute_flow_accumulation(flow_direction: np.ndarray) -> np.ndarray:
    """
    Compute flow accumulation from a D8 flow direction grid.

    Args:
        flow_direction: int8 2D array from compute_flow_direction().
                        -1 = no data / no flow.

    Returns:
        flow_acc: int32 2D array, same shape. Value = number of upstream
                  cells contributing to each cell (0 = headwater).
    """
    rows, cols = flow_direction.shape
    flow_acc = np.zeros((rows, cols), dtype=np.int32)

    # ── Step 1: compute in-degree for every cell ──────────────────────────
    in_degree = np.zeros((rows, cols), dtype=np.int32)

    for r in range(rows):
        for c in range(cols):
            d = int(flow_direction[r, c])
            if d < 0:
                continue
            dr, dc = D8_OFFSETS[d]
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                in_degree[nr, nc] += 1

    # ── Step 2: seed queue with all headwater cells (in_degree == 0) ──────
    queue: deque = deque()
    for r in range(rows):
        for c in range(cols):
            if flow_direction[r, c] >= 0 and in_degree[r, c] == 0:
                queue.append((r, c))

    # ── Step 3: topological propagation ──────────────────────────────────
    processed = 0
    while queue:
        r, c = queue.popleft()
        processed += 1

        d = int(flow_direction[r, c])
        if d < 0:
            continue

        dr, dc = D8_OFFSETS[d]
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols):
            continue

        flow_acc[nr, nc] += flow_acc[r, c] + 1
        in_degree[nr, nc] -= 1
        if in_degree[nr, nc] == 0:
            queue.append((nr, nc))

    logger.debug(
        "Flow accumulation: processed %d cells, max acc = %d.",
        processed,
        int(flow_acc.max()),
    )

    return flow_acc

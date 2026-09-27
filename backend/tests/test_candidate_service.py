"""Unit tests for the candidate service's selection-polygon hard filter.

Context: the area-select DEM grid is deliberately padded 10% beyond the
polygon the user actually drew (avoids flow-routing edge artifacts), so a
candidate/catchment can legitimately land in that padding margin — visibly
outside the box the user drew on the map. `selection_polygon` restricts
*accepted* candidates to the literal drawn area; it's only passed for the
area-select path (None for contour uploads, which have no narrower
user-drawn shape to restrict to)."""

from concurrent.futures import Future
from unittest.mock import patch

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from app.models.candidate import CandidateStatus
from app.models.catchment import FlowData
from app.models.contour import BoundingBox
from app.models.terrain import TerrainModel, TerrainStatistics
from app.services.candidate_service import generate_candidates

_BBOX = BoundingBox(min_lon=81.28, min_lat=21.26, max_lon=81.29, max_lat=21.27)


def _build_terrain_with_single_pit(pit_row=2, pit_col=2):
    """A flat 5x5 DEM with one clear depression cell — guarantees exactly
    one depression seed, with no flow-convergence noise (a single non-zero
    flow_accumulation cell at the same location avoids an empty-array
    percentile crash without introducing a second, unrelated seed)."""
    shape = (5, 5)
    dem = np.full(shape, 100.0)
    dem[pit_row, pit_col] = 95.0
    filled_dem = dem.copy()
    filled_dem[pit_row, pit_col] = 100.0  # depression-fill raised it back up
    slope = np.zeros(shape)

    stats = TerrainStatistics(
        min_elevation_m=95.0,
        max_elevation_m=100.0,
        mean_elevation_m=99.0,
        elevation_range_m=5.0,
        avg_slope_deg=0.0,
        max_slope_deg=0.0,
        dem_resolution_m=30.0,
        grid_rows=5,
        grid_cols=5,
    )
    terrain = TerrainModel(
        dem=dem,
        slope=slope,
        filled_dem=filled_dem,
        stats=stats,
        origin_x=300000.0,
        origin_y=2400000.0,
        resolution_m=30.0,
        projected_crs="EPSG:32644",
    )

    flow_direction = np.full(shape, -1, dtype=np.int8)
    flow_accumulation = np.zeros(shape, dtype=np.int32)
    flow_accumulation[pit_row, pit_col] = 1  # only non-zero cell: no extra seed
    flow_data = FlowData(flow_direction=flow_direction, flow_accumulation=flow_accumulation)

    return terrain, flow_data


def _find_candidate_at(candidates, terrain, row, col):
    x, y = terrain.cell_to_projected(row, col)
    for c in candidates:
        cx, cy = terrain.cell_to_projected(c.grid_row, c.grid_col)
        if cx == x and cy == y:
            return c
    return None


@patch("app.services.candidate_service.build_exclusion_union", return_value=(None, []))
def test_candidate_outside_selection_polygon_is_rejected(_mock_exclusion):
    terrain, flow_data = _build_terrain_with_single_pit()
    pit_x, pit_y = terrain.cell_to_projected(2, 2)

    # Nowhere near the pit cell.
    far_away_polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    assert not far_away_polygon.contains(Point(pit_x, pit_y))

    candidates, warnings = generate_candidates(
        terrain, flow_data, _BBOX, selection_polygon=far_away_polygon
    )

    candidate = _find_candidate_at(candidates, terrain, 2, 2)
    assert candidate is not None
    assert candidate.status == CandidateStatus.REJECTED_OUTSIDE_SELECTION
    assert "outside the area you selected" in candidate.rejection_reason
    assert warnings == []


@patch("app.services.candidate_service.build_exclusion_union", return_value=(None, []))
def test_candidate_inside_selection_polygon_is_not_rejected_for_that_reason(_mock_exclusion):
    terrain, flow_data = _build_terrain_with_single_pit()
    pit_x, pit_y = terrain.cell_to_projected(2, 2)

    covers_everything = Polygon(
        [
            (pit_x - 1000, pit_y - 1000),
            (pit_x + 1000, pit_y - 1000),
            (pit_x + 1000, pit_y + 1000),
            (pit_x - 1000, pit_y + 1000),
        ]
    )

    candidates, _warnings = generate_candidates(
        terrain, flow_data, _BBOX, selection_polygon=covers_everything
    )

    candidate = _find_candidate_at(candidates, terrain, 2, 2)
    assert candidate is not None
    assert candidate.status != CandidateStatus.REJECTED_OUTSIDE_SELECTION


@patch("app.services.candidate_service.build_exclusion_union", return_value=(None, []))
def test_no_selection_polygon_means_no_such_rejection(_mock_exclusion):
    """The contour-upload path passes selection_polygon=None — behaviour
    must stay exactly as before this filter was added."""
    terrain, flow_data = _build_terrain_with_single_pit()

    candidates, _warnings = generate_candidates(terrain, flow_data, _BBOX, selection_polygon=None)

    assert all(c.status != CandidateStatus.REJECTED_OUTSIDE_SELECTION for c in candidates)


@patch("app.services.candidate_service.build_exclusion_union")
def test_uses_pre_resolved_exclusion_future_instead_of_calling_build_exclusion_union(
    mock_build_exclusion,
):
    """The selected-area path launches build_exclusion_union in a background
    thread at the same time as the elevation fetch (so it overlaps instead
    of stacking after it) and passes the resulting Future through instead
    of calling build_exclusion_union again here."""
    terrain, flow_data = _build_terrain_with_single_pit()

    future: Future = Future()
    future.set_result((None, ["some warning"]))

    candidates, warnings = generate_candidates(
        terrain, flow_data, _BBOX, exclusion_union_future=future
    )

    assert warnings == ["some warning"]
    assert candidates  # pipeline still ran to completion
    mock_build_exclusion.assert_not_called()


@patch("app.services.candidate_service.build_exclusion_union")
def test_exclusion_future_exception_degrades_gracefully(mock_build_exclusion):
    """A background-thread exception must never surface as a hard failure —
    it degrades exactly like an unreachable Overpass does when fetched
    synchronously (skip the filter, add a warning)."""
    terrain, flow_data = _build_terrain_with_single_pit()

    future: Future = Future()
    future.set_exception(RuntimeError("background fetch blew up"))

    candidates, warnings = generate_candidates(
        terrain, flow_data, _BBOX, exclusion_union_future=future
    )

    assert candidates  # still produced a result, didn't raise
    assert any("skipped" in w.lower() for w in warnings)
    mock_build_exclusion.assert_not_called()

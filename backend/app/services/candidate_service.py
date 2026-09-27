"""
Candidate Service
==================
Generates pond candidate locations from terrain and flow data.

Strategy:
  Two complementary seed types:
  1. Depression seeds — cells that were raised during depression filling
     (filled_dem > raw_dem), indicating genuine terrain bowls.
  2. Flow convergence seeds — cells with high flow accumulation values
     (top-N percentile), indicating drainage convergence points.

  Seeds from both types are merged, clustered, and filtered using:
  - Hard filter: slope > MAX_SLOPE_DEG → rejected
  - Hard filter: catchment < MIN_CATCHMENT_KM2 → rejected
  - Spatial NMS: candidates too close together → keep the best one

  For each surviving candidate, a full catchment is delineated.
"""

from __future__ import annotations

from concurrent.futures import Future
import logging
from typing import List, Optional, Tuple

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point, Polygon

from app.algorithms.scoring import score_and_rank_candidates
from app.config import settings
from app.models.candidate import CandidateStatus, PondCandidate
from app.models.catchment import FlowData
from app.models.contour import BoundingBox
from app.models.terrain import TerrainModel
from app.services.catchment_service import get_catchment
from app.services.landuse_service import build_exclusion_union
from app.utils.geo import haversine_m

logger = logging.getLogger(__name__)


def generate_candidates(
    terrain: TerrainModel,
    flow_data: FlowData,
    bbox: BoundingBox,
    selection_polygon: Optional[Polygon] = None,
    exclusion_union_future: Optional["Future"] = None,
) -> Tuple[List[PondCandidate], List[str]]:
    """
    Generate and evaluate all pond candidates.

    Args:
        terrain:   TerrainModel with dem, filled_dem, slope.
        flow_data: FlowData with flow_direction and flow_accumulation.
        bbox:      WGS84 bounding box of the analysis area, used to fetch
                   land-use exclusion geometries (buildings/roads/rivers) —
                   ignored if exclusion_union_future is supplied.
        selection_polygon: The user's drawn polygon, already projected into
                   terrain.projected_crs (selected-area analysis only). The
                   DEM grid is padded beyond this polygon to avoid flow-
                   routing edge artifacts, so a candidate can otherwise land
                   in that padding margin, outside the area the user asked
                   about — this rejects those. None (contour-upload path)
                   skips this filter: there's no user-drawn shape narrower
                   than the contour extent to restrict to.
        exclusion_union_future: A `build_exclusion_union(...)` call already
                   launched in a background thread (selected-area analysis
                   only), started at the same time as the elevation fetch
                   since land-use only needs the bbox, not the terrain. When
                   supplied, its result is used instead of calling
                   build_exclusion_union again here. None (contour-upload
                   path) calls it synchronously as before.

    Returns:
        (candidates, warnings) — candidates scored and ranked; warnings
        covers non-fatal issues like the land-use filter being unavailable.
    """
    cfg = settings

    # build_exclusion_union already no-ops (returns None, []) when the
    # filter is disabled in settings or Overpass can't be reached.
    if exclusion_union_future is not None:
        try:
            exclusion_union, constraint_warnings = exclusion_union_future.result()
        except Exception as exc:
            logger.warning("Background land-use fetch failed unexpectedly: %s", exc)
            exclusion_union, constraint_warnings = None, [
                "Land-use constraint checking was skipped: background fetch failed unexpectedly."
            ]
    else:
        exclusion_union, constraint_warnings = build_exclusion_union(bbox, terrain.projected_crs)

    # ── 1. Depression seeds ───────────────────────────────────────────────
    depression_seeds = _find_depression_seeds(terrain)
    logger.info("Found %d depression seeds.", len(depression_seeds))

    # ── 2. Flow convergence seeds ─────────────────────────────────────────
    convergence_seeds = _find_convergence_seeds(flow_data, cfg.flow_acc_percentile)
    logger.info("Found %d flow convergence seeds.", len(convergence_seeds))

    # ── 3. Merge and deduplicate ──────────────────────────────────────────
    all_seeds: List[Tuple[int, int, str]] = []  # (row, col, seed_type)
    seen = set()
    for r, c in depression_seeds:
        if (r, c) not in seen:
            all_seeds.append((r, c, "depression"))
            seen.add((r, c))
    for r, c in convergence_seeds:
        if (r, c) not in seen:
            all_seeds.append((r, c, "flow_convergence"))
            seen.add((r, c))

    # Sort by flow accumulation descending
    all_seeds.sort(key=lambda s: -int(flow_data.flow_accumulation[s[0], s[1]]))

    # ── 4. Spatial NMS — remove clusters, keep highest acc in each ────────
    selected_seeds = _spatial_nms(all_seeds, terrain, cfg.min_candidate_distance_m)
    logger.info("After spatial NMS: %d candidate seeds.", len(selected_seeds))

    # ── 5. Build and evaluate candidates ─────────────────────────────────
    candidates: List[PondCandidate] = []
    transformer = Transformer.from_crs(terrain.projected_crs, "EPSG:4326", always_xy=True)
    cid = 1

    for r, c, seed_type in selected_seeds:
        if cid > cfg.max_candidates * 3:  # Evaluate at most 3× max before hard limit
            break

        x, y = terrain.cell_to_projected(r, c)
        lon, lat = transformer.transform(x, y)

        elev = float(terrain.dem[r, c])
        slope = float(terrain.slope[r, c])
        flow_acc = int(flow_data.flow_accumulation[r, c])
        depression_delta = float(max(0.0, terrain.filled_dem[r, c] - terrain.dem[r, c]))

        candidate = PondCandidate(
            candidate_id=f"C{cid}",
            seed_type=seed_type,
            grid_row=r,
            grid_col=c,
            latitude=round(lat, 6),
            longitude=round(lon, 6),
            elevation_m=round(elev, 2),
            slope_deg=round(slope, 2),
            flow_accumulation=flow_acc,
            depression_delta_m=round(depression_delta, 2),
            catchment_area_km2=0.0,
            catchment_boundary_geojson={"type": "Polygon", "coordinates": []},
        )

        # ── Hard filter: slope ────────────────────────────────────────────
        if slope > cfg.max_slope_deg:
            candidate.status = CandidateStatus.REJECTED_SLOPE
            candidate.rejection_reason = (
                f"Slope {slope:.1f}° exceeds maximum {cfg.max_slope_deg}°"
            )
            candidates.append(candidate)
            cid += 1
            continue

        # ── Hard filter: outside the user's drawn selection ───────────────
        if selection_polygon is not None and not selection_polygon.contains(Point(x, y)):
            candidate.status = CandidateStatus.REJECTED_OUTSIDE_SELECTION
            candidate.rejection_reason = (
                "Falls in the DEM's padding margin, outside the area you selected on the map"
            )
            candidates.append(candidate)
            cid += 1
            continue

        # ── Hard filter: land-use constraint (buildings/roads/rivers) ─────
        if exclusion_union is not None and Point(x, y).intersects(exclusion_union):
            candidate.status = CandidateStatus.REJECTED_CONSTRAINT
            candidate.rejection_reason = (
                "Location falls within a buffered building, road, waterway, "
                "or power line (OpenStreetMap)"
            )
            candidates.append(candidate)
            cid += 1
            continue

        # ── Delineate catchment ───────────────────────────────────────────
        try:
            catchment = get_catchment(r, c, terrain, flow_data)
        except Exception as exc:
            logger.warning("Catchment delineation failed for (%d,%d): %s", r, c, exc)
            candidate.status = CandidateStatus.REJECTED_BOUNDARY
            candidate.rejection_reason = f"Catchment delineation error: {exc}"
            candidates.append(candidate)
            cid += 1
            continue

        candidate.catchment_area_km2 = round(catchment.area_km2, 4)
        candidate.catchment_boundary_geojson = catchment.boundary_geojson

        # ── Hard filter: catchment size ───────────────────────────────────
        if catchment.area_km2 < cfg.min_catchment_km2:
            candidate.status = CandidateStatus.REJECTED_CATCHMENT
            candidate.rejection_reason = (
                f"Catchment {catchment.area_km2:.4f} km² < minimum {cfg.min_catchment_km2} km²"
            )
            candidates.append(candidate)
            cid += 1
            continue

        candidates.append(candidate)
        cid += 1

    # ── 6. Score and rank accepted candidates ─────────────────────────────
    candidates = score_and_rank_candidates(
        candidates,
        w_catchment=cfg.score_weight_catchment,
        w_flow_acc=cfg.score_weight_flow_acc,
        w_slope=cfg.score_weight_slope,
        w_relief=cfg.score_weight_relief,
        w_depression=cfg.score_weight_depression,
    )

    # ── 7. Limit accepted candidates to MAX_CANDIDATES ────────────────────
    accepted = [c for c in candidates if c.status == CandidateStatus.ACCEPTED]
    rejected = [c for c in candidates if c.status != CandidateStatus.ACCEPTED]

    if len(accepted) > cfg.max_candidates:
        extra = accepted[cfg.max_candidates:]
        for c in extra:
            c.status = CandidateStatus.REJECTED_DUPLICATE
            c.rejection_reason = "Exceeds maximum candidate limit"
        accepted = accepted[: cfg.max_candidates]

    final = accepted + rejected

    accepted_count = sum(1 for c in final if c.status == CandidateStatus.ACCEPTED)
    logger.info(
        "Candidate generation complete: %d accepted, %d rejected.",
        accepted_count,
        len(final) - accepted_count,
    )

    return final, constraint_warnings


# ── Seed finders ──────────────────────────────────────────────────────────────

def _find_depression_seeds(terrain: TerrainModel) -> List[Tuple[int, int]]:
    """Find cells where depression filling raised the elevation significantly."""
    delta = terrain.filled_dem - terrain.dem
    threshold = 0.1  # at least 10 cm fill
    rows, cols = np.where(delta > threshold)
    seeds = list(zip(rows.tolist(), cols.tolist()))

    # Keep only local minima of the depression delta (avoid dense clusters)
    from scipy.ndimage import minimum_filter
    local_min = (terrain.dem == minimum_filter(terrain.dem, size=5, mode="reflect"))
    depression_local_min = [(r, c) for r, c in seeds if local_min[r, c]]

    return depression_local_min if depression_local_min else seeds[:50]


def _find_convergence_seeds(
    flow_data: FlowData,
    percentile: float,
) -> List[Tuple[int, int]]:
    """Find high flow-accumulation cells above the given percentile."""
    acc = flow_data.flow_accumulation
    threshold = np.percentile(acc[acc > 0], percentile)
    rows, cols = np.where(acc >= threshold)
    return list(zip(rows.tolist(), cols.tolist()))


def _spatial_nms(
    seeds: List[Tuple[int, int, str]],
    terrain: TerrainModel,
    min_distance_m: float,
) -> List[Tuple[int, int, str]]:
    """
    Non-maximum suppression: remove candidates within min_distance_m of a
    higher-ranked (higher flow_accumulation) candidate.
    """
    from pyproj import Transformer

    transformer = Transformer.from_crs(terrain.projected_crs, "EPSG:4326", always_xy=True)
    kept: List[Tuple[int, int, str]] = []
    kept_lonlats: List[Tuple[float, float]] = []

    for r, c, seed_type in seeds:
        x, y = terrain.cell_to_projected(r, c)
        lon, lat = transformer.transform(x, y)

        too_close = False
        for klon, klat in kept_lonlats:
            if haversine_m(lon, lat, klon, klat) < min_distance_m:
                too_close = True
                break

        if not too_close:
            kept.append((r, c, seed_type))
            kept_lonlats.append((lon, lat))

    return kept

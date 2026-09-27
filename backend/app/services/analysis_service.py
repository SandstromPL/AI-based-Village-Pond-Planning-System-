"""
Analysis Orchestrator Service
===============================
Coordinates the complete analysis pipeline in the correct order:

  [KML/KMZ parse | selected-area DEM fetch] → Terrain → Flow → Candidates
  → Rainfall → Runoff → Pond → GeoJSON

This service is the only component that knows the full pipeline order.
All other services/algorithms are independently testable.

Two public entry points share one pipeline tail:
  - run_analysis(file_bytes, filename)     — KML/KMZ contour upload.
  - run_area_analysis(polygon, resolution) — user-drawn map area (no file).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import List, Optional, Tuple

import numpy as np

from app.config import settings
from app.models.analysis import (
    AnalysisAssumptions,
    AnalysisResult,
    GeoJSONLayers,
    InputMetadata,
    RecommendedPond,
)
from app.models.candidate import CandidateStatus, PondCandidate
from app.models.contour import NormalizedContourData
from app.models.rainfall import PondSizingResult, RunoffResult
from app.models.terrain import TerrainModel
from app.services.candidate_service import generate_candidates
from app.services.catchment_service import compute_flow_data
from app.services.kml_service import parse_contour_file
from app.services.pond_service import estimate_pond_size
from app.services.rainfall_service import get_historical_rainfall
from app.services.runoff_service import estimate_runoff
from app.services.terrain_service import build_terrain_model, build_terrain_model_from_area
from app.utils import geojson as gj

logger = logging.getLogger(__name__)


def run_analysis(file_bytes: bytes, filename: str) -> AnalysisResult:
    """Run the full pond planning analysis pipeline from an uploaded KML/KMZ file."""
    logger.info("=== Starting contour-upload analysis for file: %s ===", filename)

    contour_data = parse_contour_file(file_bytes, filename)
    terrain = build_terrain_model(contour_data)

    input_metadata = InputMetadata(
        source_type="contour_upload",
        bbox=contour_data.bbox,
        filename=contour_data.source_filename,
        format=contour_data.source_format,
        contour_count=contour_data.contour_count,
        min_elevation_m=contour_data.min_elevation,
        max_elevation_m=contour_data.max_elevation,
    )

    return _run_from_terrain(terrain, input_metadata, contour_data=contour_data, warnings=[])


def run_area_analysis(
    polygon: List[Tuple[float, float]],
    resolution_m: Optional[float] = None,
) -> AnalysisResult:
    """Run the full pond planning analysis pipeline for a user-drawn map area."""
    logger.info("=== Starting selected-area analysis (%d polygon points) ===", len(polygon))

    terrain, area_warnings = build_terrain_model_from_area(polygon, resolution_m)

    input_metadata = InputMetadata(
        source_type="selected_area",
        bbox=_bbox_from_terrain(terrain),
    )

    return _run_from_terrain(
        terrain, input_metadata, contour_data=None, warnings=list(area_warnings)
    )


def _bbox_from_terrain(terrain: TerrainModel):
    """Reconstruct a WGS84 BoundingBox from a terrain grid's corners."""
    from app.models.contour import BoundingBox
    from app.utils.geo import projected_to_lonlat

    rows, cols = terrain.shape
    x0, y0 = terrain.origin_x, terrain.origin_y
    x1 = x0 + cols * terrain.resolution_m
    y1 = y0 - rows * terrain.resolution_m

    lons, lats = projected_to_lonlat(
        np.array([x0, x1]), np.array([y0, y1]), terrain.projected_crs
    )
    return BoundingBox(
        min_lon=float(min(lons)),
        min_lat=float(min(lats)),
        max_lon=float(max(lons)),
        max_lat=float(max(lats)),
    )


def _run_from_terrain(
    terrain: TerrainModel,
    input_metadata: InputMetadata,
    contour_data: Optional[NormalizedContourData],
    warnings: List[str],
) -> AnalysisResult:
    """Shared pipeline tail: flow → candidates → rainfall → runoff → pond → geojson."""
    analysis_id = str(uuid.uuid4())
    t_start = time.perf_counter()
    warnings = list(warnings)

    logger.info("[analysis %s] Computing flow direction and accumulation...", analysis_id)
    flow_data = compute_flow_data(terrain)

    logger.info("[analysis %s] Generating and evaluating pond candidates...", analysis_id)
    candidates = generate_candidates(terrain, flow_data)

    accepted = [c for c in candidates if c.status == CandidateStatus.ACCEPTED]
    rejected = [c for c in candidates if c.status != CandidateStatus.ACCEPTED]

    if not accepted:
        warnings.append(
            "No valid pond candidates found after applying terrain/catchment filters. "
            "Consider adjusting MAX_SLOPE_DEG or MIN_CATCHMENT_KM2 in settings."
        )
        logger.warning("No accepted candidates found.")

    best: Optional[PondCandidate] = next((c for c in accepted if c.rank == 1), None)

    logger.info("[analysis %s] Fetching historical rainfall data...", analysis_id)
    ref_lat = best.latitude if best else input_metadata.bbox.center_lat
    ref_lon = best.longitude if best else input_metadata.bbox.center_lon
    rainfall = get_historical_rainfall(ref_lat, ref_lon)

    logger.info("[analysis %s] Estimating annual runoff...", analysis_id)
    catchment_km2 = best.catchment_area_km2 if best else 0.0
    runoff = estimate_runoff(rainfall, catchment_km2)

    logger.info("[analysis %s] Estimating planning-level pond storage...", analysis_id)
    slope_at_best = best.slope_deg if best else None
    pond = estimate_pond_size(runoff, slope_at_best)

    if rainfall.status != "success":
        warnings.append(
            "Historical rainfall is unavailable, so expected water volume and pond storage "
            "could not be estimated. " + rainfall.message
        )

    geojson_layers = _build_geojson_layers(contour_data, candidates, best, runoff, pond)

    recommended = None
    if best:
        recommended = RecommendedPond(
            candidate_id=best.candidate_id,
            latitude=best.latitude,
            longitude=best.longitude,
            elevation_m=best.elevation_m,
            slope_deg=best.slope_deg,
            catchment_area_km2=best.catchment_area_km2,
            catchment_boundary_geojson=best.catchment_boundary_geojson,
            score=best.score,
            rank=best.rank,
            reasoning=best.reasoning,
            expected_annual_collection_m3=runoff.annual_runoff_m3,
            planned_storage_m3=pond.estimated_storage_m3,
        )

    t_end = time.perf_counter()
    processing_time = round(t_end - t_start, 2)

    logger.info(
        "=== Analysis %s complete in %.2fs. Candidates: %d accepted, %d rejected. ===",
        analysis_id,
        processing_time,
        len(accepted),
        len(rejected),
    )

    return AnalysisResult(
        analysis_id=analysis_id,
        status="success" if accepted else "partial",
        processing_time_s=processing_time,
        input=input_metadata,
        terrain=terrain.stats,
        candidates=candidates,
        recommended=recommended,
        all_candidates_count=len(candidates),
        accepted_candidates_count=len(accepted),
        rejected_candidates_count=len(rejected),
        rainfall=rainfall,
        runoff=runoff,
        pond=pond,
        geojson_layers=geojson_layers,
        assumptions=_build_assumptions(rainfall.source, runoff.runoff_coefficient),
        warnings=warnings,
    )


# ── GeoJSON layer builder ─────────────────────────────────────────────────────

def _build_geojson_layers(
    contour_data: Optional[NormalizedContourData],
    candidates: List[PondCandidate],
    best: Optional[PondCandidate],
    runoff: RunoffResult,
    pond: PondSizingResult,
) -> GeoJSONLayers:
    """Assemble all GeoJSON layers for the frontend."""

    # Contour lines (only present for the KML/KMZ upload path)
    if contour_data is not None:
        contour_features = []
        for contour in contour_data.contours:
            coords = [[lon, lat] for lon, lat in contour.coordinates]
            contour_features.append(
                gj.linestring_feature(
                    coords,
                    properties={
                        "elevation_m": contour.elevation_m,
                        "contour_id": contour.contour_id,
                    },
                )
            )
        contour_fc = gj.feature_collection(contour_features)
    else:
        contour_fc = gj.feature_collection([])

    # Candidate points
    candidate_features = []
    for c in candidates:
        candidate_features.append(
            gj.point_feature(
                c.longitude,
                c.latitude,
                properties={
                    "id": c.candidate_id,
                    "status": c.status.value,
                    "score": c.score,
                    "rank": c.rank,
                    "elevation_m": c.elevation_m,
                    "slope_deg": c.slope_deg,
                    "catchment_area_km2": c.catchment_area_km2,
                    "seed_type": c.seed_type,
                    "rejection_reason": c.rejection_reason,
                    "expected_annual_collection_m3": (
                        runoff.annual_runoff_m3 if c.rank == 1 else None
                    ),
                    "planned_storage_m3": (
                        pond.estimated_storage_m3 if c.rank == 1 else None
                    ),
                },
            )
        )
    candidates_fc = gj.feature_collection(candidate_features)

    # Recommended location point
    if best:
        recommended_feature = gj.point_feature(
            best.longitude,
            best.latitude,
            properties={
                "id": best.candidate_id,
                "score": best.score,
                "catchment_area_km2": best.catchment_area_km2,
                "expected_annual_collection_m3": runoff.annual_runoff_m3,
                "planned_storage_m3": pond.estimated_storage_m3,
                "volume_status": pond.status,
                "reasoning": best.reasoning,
            },
        )
    else:
        recommended_feature = gj.feature(
            geometry={"type": "Point", "coordinates": []},
            properties={"message": "No valid candidate found"},
        )

    # Catchment boundaries for all accepted candidates
    catchment_features = []
    for c in candidates:
        if (
            c.status == CandidateStatus.ACCEPTED
            and c.catchment_boundary_geojson.get("coordinates")
        ):
            catchment_features.append(
                gj.feature(
                    geometry=c.catchment_boundary_geojson,
                    properties={
                        "candidate_id": c.candidate_id,
                        "rank": c.rank,
                        "area_km2": c.catchment_area_km2,
                        "is_recommended": c.rank == 1,
                    },
                )
            )
    catchment_fc = gj.feature_collection(catchment_features)

    return GeoJSONLayers(
        contour_lines=contour_fc,
        candidates=candidates_fc,
        recommended_location=recommended_feature,
        catchment_boundaries=catchment_fc,
        drainage_network=None,  # Future work: extract from flow accumulation high-value cells
    )


def _build_assumptions(
    rainfall_source: str,
    runoff_coefficient: Optional[float],
) -> AnalysisAssumptions:
    cfg = settings
    return AnalysisAssumptions(
        dem_resolution_m=cfg.dem_resolution_m,
        dem_interp_method=cfg.dem_interp_method,
        max_slope_filter_deg=cfg.max_slope_deg,
        flow_acc_threshold_percentile=cfg.flow_acc_percentile,
        min_candidate_distance_m=cfg.min_candidate_distance_m,
        min_catchment_km2=cfg.min_catchment_km2,
        max_candidates=cfg.max_candidates,
        score_weights={
            "catchment": cfg.score_weight_catchment,
            "flow_accumulation": cfg.score_weight_flow_acc,
            "slope": cfg.score_weight_slope,
            "relief": cfg.score_weight_relief,
            "depression": cfg.score_weight_depression,
        },
        rainfall_source=rainfall_source,
        runoff_coefficient=runoff_coefficient,
    )

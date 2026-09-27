"""
Analysis Orchestrator Service
===============================
Coordinates the complete analysis pipeline in the correct order:

  KML/KMZ parse → Terrain → Flow → Candidates → Rainfall → Runoff → Pond → GeoJSON

This service is the only component that knows the full pipeline order.
All other services/algorithms are independently testable.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import List, Optional

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
from app.services.candidate_service import generate_candidates
from app.services.catchment_service import compute_flow_data
from app.services.kml_service import parse_contour_file
from app.services.pond_service import estimate_pond_size
from app.services.rainfall_service import get_historical_rainfall
from app.services.runoff_service import estimate_runoff
from app.services.terrain_service import build_terrain_model
from app.utils import geojson as gj

logger = logging.getLogger(__name__)


def run_analysis(file_bytes: bytes, filename: str) -> AnalysisResult:
    """
    Run the full pond planning analysis pipeline.

    Args:
        file_bytes: Raw bytes of the uploaded KML/KMZ file.
        filename:   Original filename.

    Returns:
        AnalysisResult containing all pipeline outputs.
    """
    analysis_id = str(uuid.uuid4())
    t_start = time.perf_counter()
    warnings: List[str] = []

    logger.info("=== Starting analysis %s for file: %s ===", analysis_id, filename)

    # ── Step 1: Parse KML/KMZ ────────────────────────────────────────────
    logger.info("[1/7] Parsing contour file...")
    contour_data = parse_contour_file(file_bytes, filename)

    # ── Step 2: Build terrain model ───────────────────────────────────────
    logger.info("[2/7] Building terrain model (DEM + slope + depression fill)...")
    terrain = build_terrain_model(contour_data)

    # ── Step 3: Compute flow data ─────────────────────────────────────────
    logger.info("[3/7] Computing flow direction and accumulation...")
    flow_data = compute_flow_data(terrain)

    # ── Step 4: Generate candidates ───────────────────────────────────────
    logger.info("[4/7] Generating and evaluating pond candidates...")
    candidates = generate_candidates(terrain, flow_data)

    accepted = [c for c in candidates if c.status == CandidateStatus.ACCEPTED]
    rejected = [c for c in candidates if c.status != CandidateStatus.ACCEPTED]

    if not accepted:
        warnings.append(
            "No valid pond candidates found after applying terrain/catchment filters. "
            "Consider adjusting MAX_SLOPE_DEG or MIN_CATCHMENT_KM2 in settings."
        )
        logger.warning("No accepted candidates found.")

    # Best candidate = rank 1 (highest score)
    best: Optional[PondCandidate] = next(
        (c for c in accepted if c.rank == 1), None
    )

    # ── Step 5: Rainfall (placeholder) ───────────────────────────────────
    logger.info("[5/7] Fetching rainfall data (placeholder)...")
    ref_lat = best.latitude if best else contour_data.bbox.center_lat
    ref_lon = best.longitude if best else contour_data.bbox.center_lon
    rainfall = get_historical_rainfall(ref_lat, ref_lon)

    # ── Step 6: Runoff estimation (placeholder) ───────────────────────────
    logger.info("[6/7] Estimating runoff (placeholder)...")
    catchment_km2 = best.catchment_area_km2 if best else 0.0
    runoff = estimate_runoff(rainfall, catchment_km2)

    # ── Step 7: Pond sizing (placeholder) ─────────────────────────────────
    logger.info("[7/7] Estimating pond size (placeholder)...")
    slope_at_best = best.slope_deg if best else None
    pond = estimate_pond_size(runoff, slope_at_best)

    # ── Build GeoJSON layers ──────────────────────────────────────────────
    geojson_layers = _build_geojson_layers(contour_data, candidates, best)

    # ── Build recommended result ──────────────────────────────────────────
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
        input=InputMetadata(
            filename=contour_data.source_filename,
            format=contour_data.source_format,
            contour_count=contour_data.contour_count,
            min_elevation_m=contour_data.min_elevation,
            max_elevation_m=contour_data.max_elevation,
            bbox=contour_data.bbox,
        ),
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
        assumptions=_build_assumptions(),
        warnings=warnings,
    )


# ── GeoJSON layer builder ─────────────────────────────────────────────────────

def _build_geojson_layers(
    contour_data: NormalizedContourData,
    candidates: List[PondCandidate],
    best: Optional[PondCandidate],
) -> GeoJSONLayers:
    """Assemble all GeoJSON layers for the frontend."""

    # Contour lines
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
        drainage_network=None,  # Phase 3: extract from flow accumulation high-value cells
    )


def _build_assumptions() -> AnalysisAssumptions:
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
        rainfall_source="placeholder",
        runoff_coefficient=None,
    )

"""
Analysis API Routes
====================
POST /analyzeContour  — upload KML/KMZ, run full analysis, return results
GET  /analysis/{id}   — retrieve a previously computed analysis
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.models.candidate import CandidateStatus
from app.models.responses import (
    AnalysisResponse,
    AssumptionsSchema,
    BBoxSchema,
    CandidateSchema,
    ErrorResponse,
    GeoJSONLayersSchema,
    InputMetadataSchema,
    LocationSchema,
    PondSchema,
    RainfallSchema,
    RecommendedSchema,
    RunoffSchema,
    ScoreBreakdownSchema,
    TerrainSchema,
)
from app.services.analysis_service import run_analysis
from app.services.kml_service import KMLParseError
from app.utils import storage

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Allowed file types ────────────────────────────────────────────────────────
_ALLOWED_EXTENSIONS = {".kml", ".kmz"}
_MAX_FILE_SIZE_MB = 50


# ─────────────────────────────────────────────────────────────────────────────
# POST /analyzeContour
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/analyzeContour",
    response_model=AnalysisResponse,
    summary="Analyze a contour map for pond site selection",
    description=(
        "Upload a contour map in KML or KMZ format. "
        "The system analyzes the terrain, computes drainage and catchment areas, "
        "identifies suitable pond locations, and returns a ranked recommendation "
        "with full geospatial layers in GeoJSON format."
    ),
    responses={
        200: {"description": "Analysis complete"},
        400: {"model": ErrorResponse, "description": "Invalid file format or parse error"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal analysis error"},
    },
    tags=["Analysis"],
)
async def analyze_contour(
    contour_map: UploadFile = File(..., description="KML or KMZ contour map file"),
):
    # ── Validate file ─────────────────────────────────────────────────────
    filename = contour_map.filename or "upload.kml"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Please upload a .kml or .kmz file.",
        )

    file_bytes = await contour_map.read()

    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > _MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_mb:.1f} MB exceeds maximum {_MAX_FILE_SIZE_MB} MB.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Run analysis ──────────────────────────────────────────────────────
    try:
        result = run_analysis(file_bytes, filename)
    except KMLParseError as exc:
        logger.warning("KML parse error for '%s': %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse contour file: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during analysis of '%s'.", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal analysis error: {exc}",
        )

    # ── Persist result ────────────────────────────────────────────────────
    storage.save(result)

    # ── Serialize and return ──────────────────────────────────────────────
    return _to_response(result)


# ─────────────────────────────────────────────────────────────────────────────
# GET /analysis/{analysis_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/analysis/{analysis_id}",
    response_model=AnalysisResponse,
    summary="Retrieve a previously computed analysis",
    responses={
        200: {"description": "Analysis found"},
        404: {"model": ErrorResponse, "description": "Analysis not found"},
    },
    tags=["Analysis"],
)
async def get_analysis(analysis_id: str):
    result = storage.get(analysis_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis '{analysis_id}' not found. "
                   "Note: results are stored in-memory and reset on server restart.",
        )
    return _to_response(result)


# ─────────────────────────────────────────────────────────────────────────────
# Response serializer
# ─────────────────────────────────────────────────────────────────────────────

def _to_response(result) -> AnalysisResponse:
    """Convert internal AnalysisResult dataclass to the Pydantic response schema."""

    bbox = result.input.bbox

    candidates_schema = []
    for c in result.candidates:
        sb = None
        if c.score_breakdown:
            sb = ScoreBreakdownSchema(
                catchment_score=c.score_breakdown.catchment_score,
                flow_score=c.score_breakdown.flow_score,
                slope_score=c.score_breakdown.slope_score,
                relief_score=c.score_breakdown.relief_score,
                depression_score=c.score_breakdown.depression_score,
                final_score=c.score_breakdown.final_score,
            )
        candidates_schema.append(
            CandidateSchema(
                id=c.candidate_id,
                rank=c.rank,
                score=c.score,
                seed_type=c.seed_type,
                location=LocationSchema(latitude=c.latitude, longitude=c.longitude),
                elevation_m=c.elevation_m,
                slope_deg=c.slope_deg,
                flow_accumulation=c.flow_accumulation,
                depression_delta_m=c.depression_delta_m,
                catchment_area_km2=c.catchment_area_km2,
                catchment_boundary=c.catchment_boundary_geojson,
                status=c.status.value,
                rejection_reason=c.rejection_reason,
                score_breakdown=sb,
                reasoning=c.reasoning,
            )
        )

    recommended_schema = None
    if result.recommended:
        r = result.recommended
        recommended_schema = RecommendedSchema(
            candidate_id=r.candidate_id,
            location=LocationSchema(latitude=r.latitude, longitude=r.longitude),
            elevation_m=r.elevation_m,
            slope_deg=r.slope_deg,
            catchment_area_km2=r.catchment_area_km2,
            catchment_boundary=r.catchment_boundary_geojson,
            score=r.score,
            rank=r.rank,
            reasoning=r.reasoning,
        )

    t = result.terrain
    gl = result.geojson_layers
    a = result.assumptions

    return AnalysisResponse(
        analysis_id=result.analysis_id,
        status=result.status,
        processing_time_s=result.processing_time_s,
        input=InputMetadataSchema(
            filename=result.input.filename,
            format=result.input.format,
            contour_count=result.input.contour_count,
            min_elevation_m=result.input.min_elevation_m,
            max_elevation_m=result.input.max_elevation_m,
            bbox=BBoxSchema(
                min_lon=bbox.min_lon,
                min_lat=bbox.min_lat,
                max_lon=bbox.max_lon,
                max_lat=bbox.max_lat,
                center_lon=bbox.center_lon,
                center_lat=bbox.center_lat,
            ),
        ),
        terrain=TerrainSchema(
            min_elevation_m=t.min_elevation_m,
            max_elevation_m=t.max_elevation_m,
            mean_elevation_m=t.mean_elevation_m,
            elevation_range_m=t.elevation_range_m,
            avg_slope_deg=t.avg_slope_deg,
            max_slope_deg=t.max_slope_deg,
            dem_resolution_m=t.dem_resolution_m,
            grid_rows=t.grid_rows,
            grid_cols=t.grid_cols,
        ),
        all_candidates_count=result.all_candidates_count,
        accepted_candidates_count=result.accepted_candidates_count,
        rejected_candidates_count=result.rejected_candidates_count,
        candidates=candidates_schema,
        recommended=recommended_schema,
        rainfall=RainfallSchema(
            status=result.rainfall.status,
            source=result.rainfall.source,
            annual_avg_mm=result.rainfall.annual_avg_mm,
            monthly_avg_mm=result.rainfall.monthly_avg_mm,
            seasonal_mm=result.rainfall.seasonal_mm,
            message=result.rainfall.message,
        ),
        runoff=RunoffSchema(
            status=result.runoff.status,
            runoff_coefficient=result.runoff.runoff_coefficient,
            annual_runoff_m3=result.runoff.annual_runoff_m3,
            message=result.runoff.message,
        ),
        pond=PondSchema(
            status=result.pond.status,
            recommended_depth_m=result.pond.recommended_depth_m,
            estimated_surface_area_m2=result.pond.estimated_surface_area_m2,
            estimated_storage_m3=result.pond.estimated_storage_m3,
            message=result.pond.message,
        ),
        geojson_layers=GeoJSONLayersSchema(
            contour_lines=gl.contour_lines,
            candidates=gl.candidates,
            recommended_location=gl.recommended_location,
            catchment_boundaries=gl.catchment_boundaries,
            drainage_network=gl.drainage_network,
        ),
        assumptions=AssumptionsSchema(
            dem_resolution_m=a.dem_resolution_m,
            dem_interp_method=a.dem_interp_method,
            max_slope_filter_deg=a.max_slope_filter_deg,
            flow_acc_threshold_percentile=a.flow_acc_threshold_percentile,
            min_candidate_distance_m=a.min_candidate_distance_m,
            min_catchment_km2=a.min_catchment_km2,
            max_candidates=a.max_candidates,
            score_weights=a.score_weights,
            rainfall_source=a.rainfall_source,
            runoff_coefficient=a.runoff_coefficient,
        ),
        warnings=result.warnings,
        error_message=result.error_message,
    )

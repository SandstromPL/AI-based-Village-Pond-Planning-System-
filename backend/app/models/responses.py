"""
HTTP response Pydantic schemas for FastAPI endpoints.
These are the serializable versions of the internal dataclass models.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ── Sub-schemas ─────────────────────────────────────────────────────────────

class BBoxSchema(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    center_lon: float
    center_lat: float


class InputMetadataSchema(BaseModel):
    filename: str
    format: str
    contour_count: int
    min_elevation_m: float
    max_elevation_m: float
    bbox: BBoxSchema


class TerrainSchema(BaseModel):
    min_elevation_m: float
    max_elevation_m: float
    mean_elevation_m: float
    elevation_range_m: float
    avg_slope_deg: float
    max_slope_deg: float
    dem_resolution_m: float
    grid_rows: int
    grid_cols: int


class ScoreBreakdownSchema(BaseModel):
    catchment_score: float
    flow_score: float
    slope_score: float
    relief_score: float
    depression_score: float
    final_score: float


class LocationSchema(BaseModel):
    latitude: float
    longitude: float


class CandidateSchema(BaseModel):
    id: str
    rank: Optional[int]
    score: Optional[float]
    seed_type: str
    location: LocationSchema
    elevation_m: float
    slope_deg: float
    flow_accumulation: int
    depression_delta_m: float
    catchment_area_km2: float
    catchment_boundary: Dict[str, Any]   # GeoJSON Polygon
    status: str
    rejection_reason: Optional[str] = None
    score_breakdown: Optional[ScoreBreakdownSchema] = None
    reasoning: List[str] = []


class RecommendedSchema(BaseModel):
    candidate_id: str
    location: LocationSchema
    elevation_m: float
    slope_deg: float
    catchment_area_km2: float
    catchment_boundary: Dict[str, Any]
    score: float
    rank: int
    reasoning: List[str]


class RainfallSchema(BaseModel):
    status: str
    source: str
    annual_avg_mm: Optional[float] = None
    monthly_avg_mm: Optional[Dict[str, float]] = None
    seasonal_mm: Optional[Dict[str, float]] = None
    message: str


class RunoffSchema(BaseModel):
    status: str
    runoff_coefficient: Optional[float] = None
    annual_runoff_m3: Optional[float] = None
    message: str


class PondSchema(BaseModel):
    status: str
    recommended_depth_m: Optional[float] = None
    estimated_surface_area_m2: Optional[float] = None
    estimated_storage_m3: Optional[float] = None
    message: str


class GeoJSONLayersSchema(BaseModel):
    contour_lines: Dict[str, Any]
    candidates: Dict[str, Any]
    recommended_location: Dict[str, Any]
    catchment_boundaries: Dict[str, Any]
    drainage_network: Optional[Dict[str, Any]] = None


class AssumptionsSchema(BaseModel):
    dem_resolution_m: float
    dem_interp_method: str
    max_slope_filter_deg: float
    flow_acc_threshold_percentile: float
    min_candidate_distance_m: float
    min_catchment_km2: float
    max_candidates: int
    score_weights: Dict[str, float]
    rainfall_source: str
    runoff_coefficient: Optional[float] = None


# ── Top-level Response Schemas ───────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    """Complete response for POST /analyzeContour and GET /analysis/{id}."""

    analysis_id: str
    status: str
    processing_time_s: float

    input: InputMetadataSchema
    terrain: TerrainSchema
    all_candidates_count: int
    accepted_candidates_count: int
    rejected_candidates_count: int
    candidates: List[CandidateSchema]
    recommended: Optional[RecommendedSchema] = None

    rainfall: RainfallSchema
    runoff: RunoffSchema
    pond: PondSchema

    geojson_layers: GeoJSONLayersSchema
    assumptions: AssumptionsSchema

    warnings: List[str] = []
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.2.0"
    phase: str = "Phase 2 — Terrain & Catchment Analysis"


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
    analysis_id: Optional[str] = None

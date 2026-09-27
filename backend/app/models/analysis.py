"""
Full analysis result model — the top-level output of the pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.models.contour import NormalizedContourData, BoundingBox
from app.models.terrain import TerrainStatistics
from app.models.candidate import PondCandidate
from app.models.rainfall import NormalizedRainfallData, RunoffResult, PondSizingResult


@dataclass
class InputMetadata:
    filename: str
    format: str                  # "KML" | "KMZ"
    contour_count: int
    min_elevation_m: float
    max_elevation_m: float
    bbox: BoundingBox


@dataclass
class RecommendedPond:
    candidate_id: str
    latitude: float
    longitude: float
    elevation_m: float
    slope_deg: float
    catchment_area_km2: float
    catchment_boundary_geojson: Dict[str, Any]
    score: float
    rank: int
    reasoning: List[str]


@dataclass
class GeoJSONLayers:
    """All map-ready GeoJSON layers for the frontend."""

    contour_lines: Dict[str, Any]           # FeatureCollection
    candidates: Dict[str, Any]              # FeatureCollection
    recommended_location: Dict[str, Any]    # Feature (Point)
    catchment_boundaries: Dict[str, Any]    # FeatureCollection (Polygons)
    drainage_network: Optional[Dict[str, Any]] = None  # FeatureCollection (Lines)


@dataclass
class AnalysisAssumptions:
    """Records all configurable parameters used for this analysis run."""

    dem_resolution_m: float
    dem_interp_method: str
    max_slope_filter_deg: float
    flow_acc_threshold_percentile: float
    min_candidate_distance_m: float
    min_catchment_km2: float
    max_candidates: int
    score_weights: Dict[str, float]
    rainfall_source: str = "placeholder"
    runoff_coefficient: Optional[float] = None


@dataclass
class AnalysisResult:
    """
    The complete output of the analysis pipeline.
    Stored in-memory and returned to the API caller.
    """

    analysis_id: str
    status: str                          # "success" | "partial" | "error"
    processing_time_s: float

    input: InputMetadata
    terrain: TerrainStatistics
    candidates: List[PondCandidate]
    recommended: Optional[RecommendedPond]
    all_candidates_count: int
    accepted_candidates_count: int
    rejected_candidates_count: int

    rainfall: NormalizedRainfallData
    runoff: RunoffResult
    pond: PondSizingResult

    geojson_layers: GeoJSONLayers
    assumptions: AnalysisAssumptions

    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

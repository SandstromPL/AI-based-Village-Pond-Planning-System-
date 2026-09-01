"""
Pydantic models for pond candidate locations.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple


class CandidateStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED_SLOPE = "rejected_slope_too_steep"
    REJECTED_CATCHMENT = "rejected_catchment_too_small"
    REJECTED_BOUNDARY = "rejected_near_boundary"
    REJECTED_DUPLICATE = "rejected_duplicate"


@dataclass
class ScoreBreakdown:
    catchment_score: float   # 0-100
    flow_score: float        # 0-100
    slope_score: float       # 0-100
    relief_score: float      # 0-100
    depression_score: float  # 0-100
    final_score: float       # 0-100 weighted sum


@dataclass
class PondCandidate:
    """
    A single candidate pond location with all terrain/hydrological attributes.
    """

    candidate_id: str              # e.g. "C1", "C2"
    seed_type: str                 # "depression" | "flow_convergence"

    # Grid position
    grid_row: int
    grid_col: int

    # Geo coordinates (WGS84)
    latitude: float
    longitude: float

    # Terrain attributes
    elevation_m: float
    slope_deg: float
    flow_accumulation: int
    depression_delta_m: float      # filled_dem - raw_dem at this cell (≥0)

    # Catchment
    catchment_area_km2: float
    catchment_boundary_geojson: Dict[str, Any]   # GeoJSON Polygon, EPSG:4326
    drainage_lines_geojson: Optional[Dict[str, Any]] = None

    # Scoring
    status: CandidateStatus = CandidateStatus.ACCEPTED
    rejection_reason: Optional[str] = None
    score: Optional[float] = None
    rank: Optional[int] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    reasoning: List[str] = field(default_factory=list)

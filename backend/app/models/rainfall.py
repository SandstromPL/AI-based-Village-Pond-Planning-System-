"""
Pydantic models for rainfall, runoff, and pond sizing results.
Phase 2: these are placeholder stubs. Real implementations come in Phase 3.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class NormalizedRainfallData:
    """
    Provider-agnostic rainfall representation.
    Phase 2: all fields are None (placeholder).
    """

    status: str = "placeholder"
    source: str = "EXTERNAL_API_PLACEHOLDER"
    annual_avg_mm: Optional[float] = None
    monthly_avg_mm: Optional[Dict[str, float]] = None   # {"Jan": 12.3, ...}
    seasonal_mm: Optional[Dict[str, float]] = None       # {"monsoon": 800, ...}
    message: str = "Rainfall API not yet configured. Add provider key in .env."


@dataclass
class RunoffResult:
    """
    Rational-method runoff estimate.
    Phase 2: placeholder — C and i not yet determined.
    Rational method: Q = C × i × A
    """

    status: str = "placeholder"
    runoff_coefficient: Optional[float] = None    # C — needs soil/land-use data
    annual_runoff_m3: Optional[float] = None
    message: str = "EXTERNAL_API_PLACEHOLDER: Runoff coefficient needs soil/land-use data."


@dataclass
class PondSizingResult:
    """
    Planning-level pond dimension estimates.
    Phase 2: placeholder.
    """

    status: str = "placeholder"
    recommended_depth_m: Optional[float] = None
    estimated_surface_area_m2: Optional[float] = None
    estimated_storage_m3: Optional[float] = None
    message: str = "EXTERNAL_API_PLACEHOLDER: Pond sizing needs runoff volume from rainfall API."

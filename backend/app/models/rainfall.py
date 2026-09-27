"""
Domain models for rainfall, runoff, and pond sizing results.

All three are provider-agnostic result objects: ``status`` is "success" when
real data was retrieved/computed, or "unavailable" when an upstream input
(rainfall API, catchment area, prior stage) could not produce a usable value.
Callers should always check ``status`` before using the numeric fields.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class NormalizedRainfallData:
    """Provider-agnostic historical rainfall representation."""

    status: str = "unavailable"
    source: str = "Open-Meteo Historical Weather API"
    annual_avg_mm: Optional[float] = None
    monthly_avg_mm: Optional[Dict[str, float]] = None   # {"Jan": 12.3, ...}
    seasonal_mm: Optional[Dict[str, float]] = None       # {"monsoon_jun_sep_avg_mm": 800, ...}
    message: str = "Rainfall data has not been retrieved yet."


@dataclass
class RunoffResult:
    """
    Rational-method annual runoff estimate: Q = C × P × A.
    C = runoff coefficient, P = annual rainfall depth, A = catchment area.
    """

    status: str = "unavailable"
    runoff_coefficient: Optional[float] = None
    annual_runoff_m3: Optional[float] = None
    message: str = "Runoff has not been estimated yet."


@dataclass
class PondSizingResult:
    """Planning-level pond dimension estimates derived from annual runoff."""

    status: str = "unavailable"
    recommended_depth_m: Optional[float] = None
    estimated_surface_area_m2: Optional[float] = None
    estimated_storage_m3: Optional[float] = None
    message: str = "Pond sizing has not been estimated yet."

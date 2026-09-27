"""Provider-neutral models for rainfall, runoff, and pond-sizing results."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class NormalizedRainfallData:
    """Provider-agnostic historical rainfall representation.

    ``annual_avg_mm`` is the mean of complete calendar-year precipitation
    totals. ``monthly_avg_mm`` contains multi-year mean monthly totals.
    """

    status: str = "unavailable"
    source: str = "Open-Meteo Historical Weather API"
    annual_avg_mm: Optional[float] = None
    monthly_avg_mm: Optional[Dict[str, float]] = None   # {"Jan": 12.3, ...}
    seasonal_mm: Optional[Dict[str, float]] = None       # {"monsoon": 800, ...}
    message: str = "Historical rainfall data is unavailable."


@dataclass
class RunoffResult:
    """Annual runoff estimate using rainfall depth and catchment area."""

    status: str = "unavailable"
    runoff_coefficient: Optional[float] = None
    annual_runoff_m3: Optional[float] = None
    message: str = "Runoff cannot be estimated without historical rainfall data."


@dataclass
class PondSizingResult:
    """Planning-level pond storage and dimension estimates."""

    status: str = "unavailable"
    recommended_depth_m: Optional[float] = None
    estimated_surface_area_m2: Optional[float] = None
    estimated_storage_m3: Optional[float] = None
    message: str = "Pond storage cannot be estimated without runoff volume."

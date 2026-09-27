"""
Domain model for land-use exclusion geometries (buildings, roads, waterways,
water bodies, power lines) used to filter out pond candidates that would
sit on top of an existing structure or water feature.

Geometries are plain Shapely objects in WGS84 (EPSG:4326) — projection and
buffering into the terrain's metric CRS happens in
``app/services/landuse_service.py``, not here.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class ExclusionLayers:
    """Provider-agnostic land-use exclusion geometries for one bounding box."""

    status: str = "unavailable"
    buildings: List[Any] = field(default_factory=list)
    roads: List[Any] = field(default_factory=list)
    waterways: List[Any] = field(default_factory=list)
    water_bodies: List[Any] = field(default_factory=list)
    power_lines: List[Any] = field(default_factory=list)
    message: str = "Land-use constraint data has not been retrieved yet."

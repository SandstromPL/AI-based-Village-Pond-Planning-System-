"""
Pydantic models for normalized contour data produced by the KML/KMZ parser.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class ContourLine:
    """A single contour line extracted from the KML."""

    elevation_m: float
    coordinates: List[Tuple[float, float]]  # (longitude, latitude) in EPSG:4326
    contour_id: Optional[str] = None

    def __post_init__(self) -> None:
        if len(self.coordinates) < 2:
            raise ValueError(
                f"Contour at elevation {self.elevation_m} m has fewer than 2 coordinate pairs."
            )


@dataclass
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def center_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2.0

    @property
    def center_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2.0

    @property
    def lon_range(self) -> float:
        return self.max_lon - self.min_lon

    @property
    def lat_range(self) -> float:
        return self.max_lat - self.min_lat


@dataclass
class NormalizedContourData:
    """
    The clean, format-agnostic output of the KML/KMZ processor.
    All downstream components consume this instead of raw XML.
    """

    contours: List[ContourLine]
    bbox: BoundingBox
    source_filename: str
    source_format: str  # "KML" | "KMZ"
    crs: str = "EPSG:4326"

    @property
    def elevation_values(self) -> List[float]:
        return [c.elevation_m for c in self.contours]

    @property
    def min_elevation(self) -> float:
        return min(self.elevation_values)

    @property
    def max_elevation(self) -> float:
        return max(self.elevation_values)

    @property
    def contour_count(self) -> int:
        return len(self.contours)

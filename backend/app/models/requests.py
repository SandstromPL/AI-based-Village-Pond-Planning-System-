"""Pydantic request schemas for JSON-body API endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AreaAnalysisRequest(BaseModel):
    """A user-drawn map area to analyze, in place of a KML/KMZ upload.

    ``polygon`` is a ring of [longitude, latitude] pairs (GeoJSON coordinate
    order), at least 3 points. The polygon's bounding box is used to build
    the terrain grid — see terrain_service.build_terrain_model_from_area.
    """

    polygon: List[List[float]] = Field(..., min_length=3)
    resolution_m: Optional[float] = Field(default=None, gt=0)

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, value: List[List[float]]) -> List[List[float]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("Each polygon point must be a [longitude, latitude] pair.")
            lon, lat = point
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError(f"Invalid coordinate: [{lon}, {lat}].")
        return value

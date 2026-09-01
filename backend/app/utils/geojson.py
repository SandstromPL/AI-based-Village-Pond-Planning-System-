"""
GeoJSON serialization helpers.
Converts Shapely geometries and numpy masks to GeoJSON-compatible dicts.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import numpy as np
from shapely.geometry import mapping, shape, MultiPolygon, Polygon


def geom_to_geojson(geometry) -> Dict[str, Any]:
    """Convert a Shapely geometry to a GeoJSON geometry dict."""
    return mapping(geometry)


def feature(geometry: Dict[str, Any], properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Wrap a GeoJSON geometry in a Feature object."""
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties or {},
    }


def feature_collection(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Wrap a list of Feature dicts into a FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def point_feature(lon: float, lat: float, properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a GeoJSON Point Feature."""
    return feature(
        geometry={"type": "Point", "coordinates": [lon, lat]},
        properties=properties or {},
    )


def linestring_feature(
    coords: List[List[float]],
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a GeoJSON LineString Feature."""
    return feature(
        geometry={"type": "LineString", "coordinates": coords},
        properties=properties or {},
    )


def mask_to_geojson_polygon(
    mask: np.ndarray,
    origin_x: float,
    origin_y: float,
    resolution_m: float,
    projected_crs: str,
    target_crs: str = "EPSG:4326",
) -> Dict[str, Any]:
    """
    Convert a boolean 2D mask to a GeoJSON Polygon in the target CRS.

    Uses rasterio.features.shapes for efficient mask-to-polygon vectorization,
    then reprojects from the projected CRS to WGS84.
    """
    import rasterio.features
    from rasterio.transform import from_origin
    from pyproj import Transformer
    from shapely.geometry import shape as shapely_shape
    from shapely.ops import unary_union

    if not mask.any():
        # Empty mask — return empty polygon
        return {"type": "Polygon", "coordinates": []}

    transform = from_origin(origin_x, origin_y, resolution_m, resolution_m)
    uint8_mask = mask.astype(np.uint8)

    polygons = []
    for geom_dict, value in rasterio.features.shapes(uint8_mask, transform=transform):
        if value == 1:
            polygons.append(shapely_shape(geom_dict))

    if not polygons:
        return {"type": "Polygon", "coordinates": []}

    merged = unary_union(polygons)

    # Reproject to WGS84
    transformer = Transformer.from_crs(projected_crs, target_crs, always_xy=True)

    def reproject_coords(coords):
        result = []
        for ring in coords:
            reproj_ring = []
            for x, y in ring:
                lon, lat = transformer.transform(x, y)
                reproj_ring.append([lon, lat])
            result.append(reproj_ring)
        return result

    geom = mapping(merged)
    if geom["type"] == "Polygon":
        geom["coordinates"] = reproject_coords(geom["coordinates"])
    elif geom["type"] == "MultiPolygon":
        # Take the largest polygon
        best = max(polygons, key=lambda p: p.area)
        geom = mapping(best)
        geom["coordinates"] = reproject_coords(geom["coordinates"])

    return geom

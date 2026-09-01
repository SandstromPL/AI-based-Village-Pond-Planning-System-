"""Geospatial utility helpers: CRS detection, projection, coordinate transforms."""

from __future__ import annotations
import math
from typing import Tuple
import numpy as np
from pyproj import Proj, Transformer


def utm_zone_from_lon(lon: float) -> int:
    """Return the UTM zone number for a given longitude."""
    return int((lon + 180) / 6) + 1


def utm_epsg_from_lonlat(lon: float, lat: float) -> str:
    """
    Return the EPSG code for the UTM zone covering the given lon/lat.
    Northern hemisphere: EPSG:326XX, Southern: EPSG:327XX.
    """
    zone = utm_zone_from_lon(lon)
    if lat >= 0:
        return f"EPSG:326{zone:02d}"
    else:
        return f"EPSG:327{zone:02d}"


def get_transformer(src_crs: str, dst_crs: str) -> Transformer:
    """Return a pyproj Transformer for the given CRS pair (always_xy=True)."""
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def lonlat_to_projected(
    lons: np.ndarray,
    lats: np.ndarray,
    projected_crs: str,
    source_crs: str = "EPSG:4326",
) -> Tuple[np.ndarray, np.ndarray]:
    """Project arrays of lon/lat coordinates to a metric CRS."""
    transformer = get_transformer(source_crs, projected_crs)
    xs, ys = transformer.transform(lons, lats)
    return xs, ys


def projected_to_lonlat(
    xs: np.ndarray,
    ys: np.ndarray,
    projected_crs: str,
    target_crs: str = "EPSG:4326",
) -> Tuple[np.ndarray, np.ndarray]:
    """Inverse project arrays of metric coordinates back to lon/lat."""
    transformer = get_transformer(projected_crs, target_crs)
    lons, lats = transformer.transform(xs, ys)
    return lons, lats


def cell_area_m2(resolution_m: float) -> float:
    """Area of a single grid cell in m²."""
    return resolution_m ** 2


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

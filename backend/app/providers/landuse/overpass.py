"""Land-use exclusion geometries via the public Overpass API (OpenStreetMap).

Used by the land-use constraint filter to keep pond candidates off existing
buildings, roads, waterways, water bodies, and power lines. One combined
query per bounding box fetches all five categories in a single request
(using `out geom;` so each way's node coordinates come embedded directly —
no separate node-id resolution pass needed).

Like the rainfall and elevation providers, a failure here degrades to
``status="unavailable"`` rather than raising — the constraint filter simply
gets skipped for this analysis (see app/services/landuse_service.py), it
never blocks the core terrain/catchment pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
from shapely.geometry import LineString, Polygon

from app.config import settings
from app.models.contour import BoundingBox
from app.models.landuse import ExclusionLayers

logger = logging.getLogger(__name__)

_QUERY_TEMPLATE = """
[out:json][timeout:{timeout}];
(
  way["building"]({bbox});
  way["highway"]({bbox});
  way["waterway"]({bbox});
  way["natural"="water"]({bbox});
  way["landuse"="reservoir"]({bbox});
  way["power"="line"]({bbox});
);
out geom;
""".strip()

_cache: dict[tuple[float, float, float, float], ExclusionLayers] = {}


def fetch_exclusion_geometries(bbox: BoundingBox) -> ExclusionLayers:
    """Fetch OSM buildings/roads/waterways/water bodies/power lines for a bbox."""
    cache_key = (
        round(bbox.min_lat, 3),
        round(bbox.min_lon, 3),
        round(bbox.max_lat, 3),
        round(bbox.max_lon, 3),
    )
    if cache_key in _cache:
        return _cache[cache_key]

    result = _fetch_from_overpass(bbox)
    if result.status == "success":
        # Only cache successes — Overpass failures are often transient (a
        # timeout, a 504 under load), and caching them would otherwise
        # permanently disable the constraint filter for this bbox until
        # the process restarts, even though a retry moments later works.
        _cache[cache_key] = result
    return result


def clear_landuse_cache() -> None:
    """Clear cached Overpass results. Used by tests and operational maintenance."""
    _cache.clear()


def _fetch_from_overpass(bbox: BoundingBox) -> ExclusionLayers:
    overpass_bbox = f"{bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon}"
    query = _QUERY_TEMPLATE.format(
        timeout=int(settings.overpass_request_timeout_s), bbox=overpass_bbox
    )

    for attempt in range(settings.overpass_max_retries + 1):
        try:
            response = httpx.post(
                settings.overpass_url,
                data={"data": query},
                timeout=settings.overpass_request_timeout_s,
            )
            response.raise_for_status()
            return _parse_overpass_response(response.json())
        except httpx.TimeoutException:
            logger.warning(
                "Overpass request timed out (attempt %d/%d).",
                attempt + 1,
                settings.overpass_max_retries + 1,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Overpass request failed with HTTP %s (attempt %d/%d).",
                exc.response.status_code,
                attempt + 1,
                settings.overpass_max_retries + 1,
            )
        except httpx.ConnectError as exc:
            logger.warning(
                "Overpass connection failed (DNS/network — not retrying): %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.overpass_max_retries + 1,
            )
            break  # a same-second retry essentially never fixes a broken DNS/connection
        except httpx.HTTPError as exc:
            logger.warning(
                "Overpass request failed: %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.overpass_max_retries + 1,
            )
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Overpass returned unusable data: %s", exc)
            break

        if attempt < settings.overpass_max_retries:
            time.sleep(0.5 * (attempt + 1))

    logger.error("Overpass land-use query failed after retries; constraint filter will be skipped.")
    return ExclusionLayers(
        status="unavailable",
        message="Land-use constraint data is temporarily unavailable (could not reach Overpass).",
    )


def _parse_overpass_response(data: dict) -> ExclusionLayers:
    elements = data.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass response has no 'elements' list")

    layers = ExclusionLayers(status="success", message="Fetched from OpenStreetMap via Overpass.")

    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "way":
            continue  # v1 only handles simple ways, not multipolygon relations

        geometry = element.get("geometry")
        if not isinstance(geometry, list) or len(geometry) < 2:
            continue

        try:
            coords = [(pt["lon"], pt["lat"]) for pt in geometry]
        except (KeyError, TypeError):
            continue

        tags = element.get("tags") or {}
        is_closed = len(coords) >= 4 and coords[0] == coords[-1]

        polygon = _safe_polygon(coords) if is_closed else None
        line = _safe_linestring(coords)

        if "building" in tags and polygon is not None:
            layers.buildings.append(polygon)
        if "highway" in tags and line is not None:
            layers.roads.append(line)
        if "waterway" in tags and line is not None:
            layers.waterways.append(line)
        if (tags.get("natural") == "water" or tags.get("landuse") == "reservoir") and polygon is not None:
            layers.water_bodies.append(polygon)
        if tags.get("power") == "line" and line is not None:
            layers.power_lines.append(line)

    return layers


def _safe_polygon(coords) -> Optional[Polygon]:
    try:
        polygon = Polygon(coords)
        return polygon if polygon.is_valid and not polygon.is_empty else None
    except Exception:
        return None


def _safe_linestring(coords) -> Optional[LineString]:
    try:
        line = LineString(coords)
        return line if not line.is_empty else None
    except Exception:
        return None

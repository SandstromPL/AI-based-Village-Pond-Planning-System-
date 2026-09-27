"""Elevation lookup via the Open-Elevation public API (SRTM-based, no API key).

Used only by the map-selected-area analysis flow, where there is no KML/KMZ
contour file to derive elevation from. Point elevations are fetched in
batches and cached; a batch that fails after retries yields ``None`` for its
points rather than raising, so the caller can decide how to handle partial
coverage (see ``terrain_service.build_terrain_model_from_area``).

Points Open-Elevation could not return (including a network/DNS failure
that fails an entire batch) are retried against OpenTopoData as a second,
independent provider — different domain, different infrastructure — before
giving up on those points. This matters in practice: a network that reaches
one public API can still fail to resolve/reach another.

A hard wall-clock budget (``elevation_total_budget_s``) bounds the whole
fetch regardless of grid size or how badly both providers are behaving:
observed in production, a bad network episode made a 44x44 grid (39
batches) take ~4 minutes to fully retry through both providers — far past
any reasonable "fast and functional" bar, and past the frontend's own
timeout, so the browser gave up while the backend kept working pointlessly.
The deadline is checked before every new attempt (not just once per batch),
so remaining budget shrinks each retry's timeout too rather than only
stopping between whole batches.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import time
from typing import List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def fetch_elevations(points: List[Tuple[float, float]]) -> List[Optional[float]]:
    """Fetch elevations for a list of (latitude, longitude) points.

    Returns a list the same length as ``points``; an entry is ``None`` if
    that point's elevation could not be retrieved within the time budget.

    Batches are resolved against the point cache first, then any batches
    with cache misses are fetched from the API concurrently (bounded by
    ``elevation_max_concurrent_requests``), with the whole fetch bounded by
    ``elevation_total_budget_s`` wall-clock time.
    """
    batch_size = settings.elevation_batch_size
    raw_batches = [points[i:i + batch_size] for i in range(0, len(points), batch_size)]

    # rounded[i] = cache key per point; cached[i] = current known value or _MISS
    rounded_batches: List[List[Tuple[float, float]]] = []
    cached_batches: List[List[object]] = []
    for batch in raw_batches:
        rounded = [(round(lat, 4), round(lon, 4)) for lat, lon in batch]
        rounded_batches.append(rounded)
        cached_batches.append([_point_cache_get(lat, lon) for lat, lon in rounded])

    deadline = time.monotonic() + settings.elevation_total_budget_s

    def resolve_batch(batch_index: int) -> None:
        rounded = rounded_batches[batch_index]
        cached = cached_batches[batch_index]
        missing_indices = [i for i, v in enumerate(cached) if v is _MISS]
        if not missing_indices:
            return

        if time.monotonic() > deadline:
            logger.warning(
                "Elevation time budget exhausted before batch %d could start; "
                "%d point(s) left unfetched (will be nearest-neighbour filled).",
                batch_index,
                len(missing_indices),
            )
            return

        missing_points = [rounded[i] for i in missing_indices]
        fetched = _fetch_batch_from_api(missing_points, deadline)
        for local_i, value in zip(missing_indices, fetched):
            cached[local_i] = value
            lat, lon = rounded[local_i]
            _point_cache_set(lat, lon, value)

    batches_needing_fetch = [
        i for i, cached in enumerate(cached_batches) if _MISS in cached
    ]
    if batches_needing_fetch:
        workers = min(settings.elevation_max_concurrent_requests, len(batches_needing_fetch))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(resolve_batch, batches_needing_fetch))

    results: List[Optional[float]] = []
    for cached in cached_batches:
        results.extend(None if v is _MISS else v for v in cached)
    return results


_MISS = object()
_point_cache: dict[Tuple[float, float], Optional[float]] = {}


def _point_cache_get(lat: float, lon: float):
    return _point_cache.get((lat, lon), _MISS)


def _point_cache_set(lat: float, lon: float, value: Optional[float]) -> None:
    _point_cache[(lat, lon)] = value


def clear_elevation_cache() -> None:
    """Clear cached elevation lookups. Used by tests and operational maintenance."""
    _point_cache.clear()


def _fetch_batch_from_api(batch: List[Tuple[float, float]], deadline: float) -> List[Optional[float]]:
    """Fetch a batch from Open-Elevation, falling back to OpenTopoData for
    any points it could not provide (including a total batch failure)."""
    result = _fetch_from_open_elevation(batch, deadline)

    if settings.elevation_fallback_enabled:
        missing_indices = [i for i, v in enumerate(result) if v is None]
        if missing_indices and time.monotonic() < deadline:
            logger.warning(
                "Falling back to OpenTopoData for %d point(s) Open-Elevation could not provide.",
                len(missing_indices),
            )
            fallback_points = [batch[i] for i in missing_indices]
            fallback_values = _fetch_from_opentopodata(fallback_points, deadline)
            for local_i, value in zip(missing_indices, fallback_values):
                if value is not None:
                    result[local_i] = value

    return result


def _fetch_from_open_elevation(batch: List[Tuple[float, float]], deadline: float) -> List[Optional[float]]:
    payload = {
        "locations": [
            {"latitude": lat, "longitude": lon} for lat, lon in batch
        ]
    }

    for attempt in range(settings.elevation_max_retries + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning("Open-Elevation deadline exceeded before attempt %d.", attempt + 1)
            break
        try:
            response = httpx.post(
                settings.open_elevation_url,
                json=payload,
                timeout=min(settings.elevation_request_timeout_s, remaining),
            )
            response.raise_for_status()
            data = response.json()
            return _parse_open_elevation_response(data, expected_count=len(batch))
        except httpx.TimeoutException:
            logger.warning(
                "Open-Elevation request timed out (attempt %d/%d).",
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Open-Elevation request failed with HTTP %s (attempt %d/%d).",
                exc.response.status_code,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Open-Elevation request failed: %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Open-Elevation returned unusable data: %s", exc)
            break  # malformed payload will not improve on retry

        if attempt < settings.elevation_max_retries and time.monotonic() < deadline:
            time.sleep(min(0.5 * (attempt + 1), max(0, deadline - time.monotonic())))

    logger.error("Open-Elevation batch of %d points failed after retries.", len(batch))
    return [None] * len(batch)


def _parse_open_elevation_response(data: dict, expected_count: int) -> List[Optional[float]]:
    results = data.get("results")
    if not isinstance(results, list) or len(results) != expected_count:
        raise ValueError("Open-Elevation response 'results' missing or misaligned")

    elevations: List[Optional[float]] = []
    for item in results:
        elevation = item.get("elevation") if isinstance(item, dict) else None
        elevations.append(float(elevation) if elevation is not None else None)
    return elevations


def _fetch_from_opentopodata(batch: List[Tuple[float, float]], deadline: float) -> List[Optional[float]]:
    locations = "|".join(f"{lat},{lon}" for lat, lon in batch)

    for attempt in range(settings.elevation_max_retries + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning("OpenTopoData deadline exceeded before attempt %d.", attempt + 1)
            break
        try:
            response = httpx.get(
                settings.opentopodata_url,
                params={"locations": locations},
                timeout=min(settings.elevation_request_timeout_s, remaining),
            )
            response.raise_for_status()
            data = response.json()
            return _parse_opentopodata_response(data, expected_count=len(batch))
        except httpx.TimeoutException:
            logger.warning(
                "OpenTopoData request timed out (attempt %d/%d).",
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OpenTopoData request failed with HTTP %s (attempt %d/%d).",
                exc.response.status_code,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenTopoData request failed: %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("OpenTopoData returned unusable data: %s", exc)
            break

        if attempt < settings.elevation_max_retries and time.monotonic() < deadline:
            time.sleep(min(0.5 * (attempt + 1), max(0, deadline - time.monotonic())))

    logger.error("OpenTopoData fallback for %d point(s) failed after retries.", len(batch))
    return [None] * len(batch)


def _parse_opentopodata_response(data: dict, expected_count: int) -> List[Optional[float]]:
    results = data.get("results")
    if not isinstance(results, list) or len(results) != expected_count:
        raise ValueError("OpenTopoData response 'results' missing or misaligned")

    elevations: List[Optional[float]] = []
    for item in results:
        elevation = item.get("elevation") if isinstance(item, dict) else None
        elevations.append(float(elevation) if elevation is not None else None)
    return elevations

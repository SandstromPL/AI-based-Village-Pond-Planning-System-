"""Elevation lookup for map-selected-area analysis (no KML/KMZ file involved).

Three providers, tried in order, each independent infrastructure:

  1. OpenZenith (primary) — verified live to handle up to 2000 points per
     batch request in a couple of seconds, no API key. (A docs mirror at
     openzenith.cyopsys.com sits behind an unsolvable Cloudflare JS
     challenge for server-side clients — openzenith.org is the correct,
     working domain; don't be fooled by the other one again.)
  2. Open-Elevation — tried only for points OpenZenith could not provide.
  3. OpenTopoData — tried only for points neither of the above could provide.

A batch that fails every tier yields ``None`` for its points rather than
raising, so the caller can decide how to handle partial coverage (see
``terrain_service.build_terrain_model_from_area``, which nearest-neighbour
fills any gaps).

A hard wall-clock budget (``elevation_total_budget_s``) bounds the whole
fetch regardless of grid size or how badly the providers are behaving:
observed in production, a bad network episode made a 44x44 grid (39
Open-Elevation batches, before OpenZenith was added) take ~4 minutes to
fully retry through both fallback providers — far past any reasonable
"fast and functional" bar, and past the frontend's own timeout, so the
browser gave up while the backend kept working pointlessly. The deadline is
checked before every new attempt (not just once per batch), so remaining
budget shrinks each retry's timeout too rather than only stopping between
whole batches.
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
    ``elevation_total_budget_s`` wall-clock time. The outer batch size
    (``elevation_batch_size``) is sized for OpenZenith's large per-request
    limit; the two fallback providers get their own, much smaller, chunks
    only for whatever OpenZenith couldn't provide (see
    ``_fetch_batch_from_api``).
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
            if value is not None:
                # Only cache real values. A point that failed every provider
                # tier is often just a transient network episode (see a
                # real production incident: the same failed points were
                # served from cache on every later request, forever, even
                # after the network recovered) — leaving it uncached lets
                # the next call retry it fresh instead of repeating the
                # same failure forever.
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
    """Fetch a batch: OpenZenith first (handles the whole batch in one call),
    then Open-Elevation, then OpenTopoData for whatever's still missing —
    the latter two re-chunked into their own, much smaller, practical batch
    size, since only OpenZenith has been verified to handle batches this
    large."""
    result = _fetch_from_openzenith(batch, deadline)

    missing_indices = [i for i, v in enumerate(result) if v is None]
    if missing_indices and time.monotonic() < deadline:
        logger.warning(
            "Falling back to Open-Elevation/OpenTopoData for %d point(s) "
            "OpenZenith could not provide.",
            len(missing_indices),
        )
        fallback_points = [batch[i] for i in missing_indices]
        fallback_values = _fetch_fallback_chain(fallback_points, deadline)
        for local_i, value in zip(missing_indices, fallback_values):
            if value is not None:
                result[local_i] = value

    return result


def _fetch_fallback_chain(batch: List[Tuple[float, float]], deadline: float) -> List[Optional[float]]:
    """Open-Elevation, falling back to OpenTopoData, in sub-batches sized
    for what these two providers can reliably handle — fetched
    concurrently, not sequentially.

    This matters a lot in practice: OpenZenith failing a large batch (say
    1000 points) can itself burn most of the deadline before giving up
    (real retries against a flaky network aren't instant), leaving little
    time for the fallback. A 1000-point batch re-chunks into 20 sub-batches
    of 50 — fetching those one at a time could need 20 sequential round
    trips and realistically rescue only the first one or two before the
    deadline hits, turning a legitimately-recoverable batch into a mostly
    "missing" one. Fetching all sub-batches concurrently (same pattern
    already used for the outer batch loop in fetch_elevations) bounds the
    wall-clock cost to roughly one round trip's worth of waves instead of
    the full sequential count — observed for real: a request that would
    have ended in a hard "elevation unavailable" 502 completed
    successfully after this change (see git history for the log walkthrough)."""
    sub_size = settings.elevation_fallback_batch_size
    sub_batches = [batch[i:i + sub_size] for i in range(0, len(batch), sub_size)]
    results: List[Optional[float]] = [None] * len(batch)

    def resolve_sub_batch(index: int) -> None:
        start = index * sub_size
        sub_batch = sub_batches[index]
        if time.monotonic() > deadline:
            return

        sub_result = _fetch_from_open_elevation(sub_batch, deadline)

        if settings.elevation_fallback_enabled:
            missing_indices = [i for i, v in enumerate(sub_result) if v is None]
            if missing_indices and time.monotonic() < deadline:
                logger.warning(
                    "Falling back to OpenTopoData for %d point(s) Open-Elevation could not provide.",
                    len(missing_indices),
                )
                fallback_points = [sub_batch[i] for i in missing_indices]
                fallback_values = _fetch_from_opentopodata(fallback_points, deadline)
                for local_i, value in zip(missing_indices, fallback_values):
                    if value is not None:
                        sub_result[local_i] = value

        results[start:start + len(sub_result)] = sub_result

    if sub_batches:
        workers = min(settings.elevation_max_concurrent_requests, len(sub_batches))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(resolve_sub_batch, range(len(sub_batches))))

    return results


def _fetch_from_openzenith(batch: List[Tuple[float, float]], deadline: float) -> List[Optional[float]]:
    url = f"{settings.openzenith_url}/api/elevation/batch"
    payload = {"points": [{"lat": lat, "lon": lon} for lat, lon in batch]}

    for attempt in range(settings.openzenith_max_retries + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning("OpenZenith deadline exceeded before attempt %d.", attempt + 1)
            break
        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=min(settings.openzenith_request_timeout_s, remaining),
            )
            response.raise_for_status()
            data = response.json()
            return _parse_openzenith_response(data, batch)
        except httpx.TimeoutException:
            logger.warning(
                "OpenZenith request timed out (attempt %d/%d).",
                attempt + 1,
                settings.openzenith_max_retries + 1,
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OpenZenith request failed with HTTP %s (attempt %d/%d).",
                exc.response.status_code,
                attempt + 1,
                settings.openzenith_max_retries + 1,
            )
        except httpx.ConnectError as exc:
            logger.warning(
                "OpenZenith connection failed (DNS/network — not retrying): %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.openzenith_max_retries + 1,
            )
            break  # a same-second retry essentially never fixes a broken DNS/connection
        except httpx.HTTPError as exc:
            logger.warning(
                "OpenZenith request failed: %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.openzenith_max_retries + 1,
            )
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("OpenZenith returned unusable data: %s", exc)
            break  # malformed payload will not improve on retry

        if attempt < settings.openzenith_max_retries and time.monotonic() < deadline:
            time.sleep(min(0.5 * (attempt + 1), max(0, deadline - time.monotonic())))

    logger.error("OpenZenith batch of %d points failed after retries.", len(batch))
    return [None] * len(batch)


def _parse_openzenith_response(data: dict, requested: List[Tuple[float, float]]) -> List[Optional[float]]:
    results = data.get("results")
    if not isinstance(results, list) or len(results) != len(requested):
        raise ValueError("OpenZenith response 'results' missing or misaligned")

    elevations: List[Optional[float]] = []
    for (req_lat, req_lon), item in zip(requested, results):
        if not isinstance(item, dict):
            elevations.append(None)
            continue
        # OpenZenith echoes lat/lon per result, unlike the other two
        # providers — a cheap sanity check that positional order actually
        # matches what was requested, rather than assuming it silently.
        resp_lat, resp_lon = item.get("lat"), item.get("lon")
        if (
            resp_lat is not None
            and resp_lon is not None
            and (round(float(resp_lat), 3) != round(req_lat, 3) or round(float(resp_lon), 3) != round(req_lon, 3))
        ):
            logger.warning(
                "OpenZenith result order mismatch: requested (%.4f, %.4f), got (%.4f, %.4f).",
                req_lat, req_lon, resp_lat, resp_lon,
            )
        elevation = item.get("elevation")
        elevations.append(float(elevation) if elevation is not None else None)
    return elevations


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
        except httpx.ConnectError as exc:
            logger.warning(
                "Open-Elevation connection failed (DNS/network — not retrying): %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
            break  # a same-second retry essentially never fixes a broken DNS/connection
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
        except httpx.ConnectError as exc:
            logger.warning(
                "OpenTopoData connection failed (DNS/network — not retrying): %s (attempt %d/%d).",
                exc,
                attempt + 1,
                settings.elevation_max_retries + 1,
            )
            break  # a same-second retry essentially never fixes a broken DNS/connection
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

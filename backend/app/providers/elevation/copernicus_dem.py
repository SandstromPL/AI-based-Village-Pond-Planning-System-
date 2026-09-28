"""Elevation from Copernicus DEM GLO-30, read directly as Cloud-Optimized
GeoTIFF (COG) tiles from public cloud storage (AWS S3 Open Data) rather
than queried through a rate-limited REST API.

This is a fundamentally different resilience story than the rest of this
project's providers: there's no per-request quota to exhaust on a static
file server, so the failure mode here is network/DNS reachability to S3
itself, not rate-limiting. Tried first in the elevation cascade (see
``open_elevation.py``'s ``_fetch_batch_from_api``); the existing OpenZenith
/ Open-Elevation / OpenTopoData cascade remains the fallback for whatever
this tier can't resolve (including it being fully disabled or unreachable).

Verified live before this was written: the tile naming convention below,
no credentials needed to read the bucket, and the sampled elevation for
this project's own sample dataset's coordinates matched the real KML
contour data's known range for that area.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Dict, List, Optional, Tuple

import rasterio

from app.config import settings
from app.utils import circuit_breaker

logger = logging.getLogger(__name__)

_TILE_URL_TEMPLATE = (
    "/vsicurl/{bucket}/Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)

# Opened rasterio datasets, kept for the process lifetime — matches the
# existing point-cache's process-lifetime, in-memory pattern (see
# open_elevation.py's _point_cache) — avoids re-opening the same tile's
# HTTP connection for every batch that touches the same area.
_open_tiles: Dict[Tuple[str, int, str, int], object] = {}

# One lock per tile, guarding the open attempt itself (not just the dict
# access) — outer elevation batches run concurrently (see
# open_elevation.fetch_elevations' ThreadPoolExecutor), and a selected
# area's grid almost always fits inside a single 1x1-degree tile, so
# multiple batches racing to open the *same* tile at once was a real,
# observed bug: three concurrent batches each independently attempted
# rasterio.open() for the same tile — one succeeded in ~15s, the other
# two each wasted a further ~20s hitting their own independent DNS
# timeouts for a tile that was already (or about to be) available. With
# this lock, only the first caller actually opens the tile; the others
# block briefly and then reuse its result instead of re-fetching.
_tile_locks: Dict[Tuple[str, int, str, int], threading.Lock] = {}
_tile_locks_guard = threading.Lock()


def _tile_key(lat: float, lon: float) -> Tuple[str, int, str, int]:
    lat_tile, lon_tile = math.floor(lat), math.floor(lon)
    return (
        "N" if lat_tile >= 0 else "S",
        abs(lat_tile),
        "E" if lon_tile >= 0 else "W",
        abs(lon_tile),
    )


def fetch_from_copernicus_dem(
    points: List[Tuple[float, float]], deadline: float
) -> List[Optional[float]]:
    """Best-effort: returns None for any point whose tile couldn't be
    opened or sampled, so the caller falls through to the REST cascade.

    Args:
        points: list of (latitude, longitude) pairs.
        deadline: shared wall-clock deadline (time.monotonic()-based),
                  same convention as every other elevation provider here.
    """
    if not settings.copernicus_dem_enabled:
        return [None] * len(points)
    if circuit_breaker.is_open("copernicus-dem"):
        logger.warning("Copernicus DEM circuit open (recently unreachable); skipping.")
        return [None] * len(points)

    by_tile: Dict[Tuple[str, int, str, int], List[int]] = {}
    for i, (lat, lon) in enumerate(points):
        by_tile.setdefault(_tile_key(lat, lon), []).append(i)

    logger.info(
        "Copernicus DEM: resolving %d point(s) across %d tile(s)...", len(points), len(by_tile)
    )
    results: List[Optional[float]] = [None] * len(points)
    for tile, indices in by_tile.items():
        if time.monotonic() > deadline:
            logger.warning("Copernicus DEM deadline exceeded; %d point(s) left unfetched.", len(indices))
            break

        dataset = _get_or_open_tile(tile)
        if dataset is None:
            continue  # this tile failed to open; those points stay None

        try:
            coords = [(points[i][1], points[i][0]) for i in indices]  # rasterio wants (lon, lat)
            for i, sample in zip(indices, dataset.sample(coords)):
                results[i] = float(sample[0])
        except Exception as exc:
            logger.warning("Copernicus DEM sampling failed for tile %s: %s", tile, exc)

    resolved = sum(1 for v in results if v is not None)
    logger.info("Copernicus DEM resolved %d/%d point(s).", resolved, len(points))
    return results


def _get_or_open_tile(tile: Tuple[str, int, str, int]):
    if tile in _open_tiles:
        return _open_tiles[tile]

    with _tile_locks_guard:
        tile_lock = _tile_locks.setdefault(tile, threading.Lock())

    with tile_lock:
        # Re-check after acquiring the per-tile lock: another thread may
        # have already opened (or be opening) this exact tile while we
        # were waiting — if it succeeded, reuse its result instead of
        # making a second, redundant network call for the same data.
        if tile in _open_tiles:
            return _open_tiles[tile]
        return _open_tile_uncached(tile)


def _open_tile_uncached(tile: Tuple[str, int, str, int]):
    ns, lat, ew, lon = tile
    tile_name = f"{ns}{lat:02d}_00_{ew}{lon:03d}_00"
    url = _TILE_URL_TEMPLATE.format(
        bucket=settings.copernicus_dem_bucket_url, ns=ns, lat=lat, ew=ew, lon=lon
    )
    # Logged *before* the attempt, not just on success/failure: unlike the
    # REST providers (which log a warning per retry while they wait),
    # rasterio.open() over /vsicurl/ blocks silently for however long the
    # connection takes (observed for real: anywhere from ~0.04s to ~11s on
    # this project's own test network) — without this line, that stretch
    # looks indistinguishable from the backend simply doing nothing.
    logger.info("Fetching Copernicus DEM tile %s...", tile_name)
    start = time.monotonic()
    try:
        # GDAL's /vsicurl/ virtual filesystem takes its timeout from GDAL
        # config options, not a rasterio.open() kwarg — there is no
        # `timeout=` parameter on rasterio.open() for this.
        with rasterio.Env(
            GDAL_HTTP_TIMEOUT=int(settings.copernicus_dem_request_timeout_s),
            GDAL_HTTP_CONNECTTIMEOUT=int(settings.copernicus_dem_request_timeout_s),
        ):
            dataset = rasterio.open(url)
        logger.info(
            "Copernicus DEM tile %s opened in %.2fs.", tile_name, time.monotonic() - start
        )
        _open_tiles[tile] = dataset
        return dataset
    except Exception as exc:
        logger.warning(
            "Could not open Copernicus DEM tile %s after %.2fs: %s",
            tile_name, time.monotonic() - start, exc,
        )
        circuit_breaker.trip("copernicus-dem", settings.circuit_breaker_cooldown_s)
        return None


def clear_tile_cache() -> None:
    """Close and drop all cached open tile datasets. Used by tests."""
    for dataset in _open_tiles.values():
        try:
            dataset.close()
        except Exception:
            pass
    _open_tiles.clear()
    with _tile_locks_guard:
        _tile_locks.clear()

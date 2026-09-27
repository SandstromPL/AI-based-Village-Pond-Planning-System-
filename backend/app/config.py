"""
Application configuration using Pydantic BaseSettings.
All values can be overridden via environment variables or a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Server ──────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "info"

    # ── Terrain Processing ──────────────────────────────────────────────────
    dem_resolution_m: float = Field(default=30.0, gt=0)
    dem_bbox_padding_frac: float = Field(default=0.10, ge=0, le=1)
    dem_interp_method: str = "linear"  # linear | cubic | nearest

    # ── Candidate Generation ────────────────────────────────────────────────
    flow_acc_percentile: float = Field(default=99.0, ge=50, le=100)
    max_slope_deg: float = Field(default=15.0, gt=0)
    min_candidate_distance_m: float = Field(default=100.0, gt=0)
    max_candidates: int = Field(default=5, ge=1, le=20)
    min_catchment_km2: float = Field(default=0.005, gt=0)

    # ── Scoring Weights ─────────────────────────────────────────────────────
    score_weight_catchment: float = 0.35
    score_weight_flow_acc: float = 0.25
    score_weight_slope: float = 0.20
    score_weight_relief: float = 0.10
    score_weight_depression: float = 0.10

    # ── Elevation: OpenZenith (primary) ──────────────────────────────────────
    # Verified live: GET /api/elevation and POST /api/elevation/batch (up to
    # 2000 points/request) both work with no API key. openzenith.org is the
    # correct domain — a docs mirror at openzenith.cyopsys.com sits behind an
    # unsolvable Cloudflare JS challenge for server-side clients; don't use it.
    openzenith_url: str = "https://openzenith.org"
    # Kept fairly tight (vs. the 45s total budget): OpenZenith normally
    # responds in 1-3s even for large batches, so this is generous for the
    # happy path, but a batch failing both attempts at the max timeout
    # would otherwise burn most of the whole deadline by itself, leaving
    # the Open-Elevation/OpenTopoData fallback chain almost no time to
    # actually rescue those points (observed for real in production logs).
    openzenith_request_timeout_s: float = Field(default=15.0, gt=0, le=60)
    openzenith_max_retries: int = Field(default=1, ge=0, le=5)

    # ── Rainfall: Open-Meteo Historical Weather API ─────────────────────────
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    rainfall_history_start_year: int = Field(default=2015, ge=1900)
    rainfall_history_end_year: int | None = Field(default=None, ge=1900)
    rainfall_request_timeout_s: float = Field(default=10.0, gt=0, le=60)

    # ── Planning-level runoff and pond assumptions ──────────────────────────
    # The default coefficient represents mixed agricultural/semi-pervious land.
    # It remains explicit until a land-cover provider is integrated.
    runoff_coefficient_default: float = Field(default=0.35, ge=0, le=1)
    pond_retention_factor: float = Field(default=0.80, gt=0, le=1)
    pond_default_depth_m: float = Field(default=3.0, gt=0)
    pond_steep_slope_threshold_deg: float = Field(default=5.0, gt=0)
    pond_steep_slope_depth_m: float = Field(default=2.0, gt=0)

    # [EXTERNAL_API_PLACEHOLDER: NASA POWER]
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"

    # [EXTERNAL_API_PLACEHOLDER: IMD]
    imd_api_key: str = "PLACEHOLDER"
    imd_base_url: str = "https://imdpune.gov.in/api"

    # ── Elevation: Open-Elevation API (fallback, for map-selected-area analysis) ──
    open_elevation_url: str = "https://api.open-elevation.com/api/v1/lookup"
    elevation_request_timeout_s: float = Field(default=15.0, gt=0, le=60)
    # OpenZenith (primary) handles up to 2000 points/request — verified live
    # at ~2.4s for 2000 and <1s for 1000, so this is the *outer* batching
    # unit fetch_elevations() uses, kept safely under that cap. Points
    # OpenZenith couldn't provide are re-chunked into elevation_fallback_batch_size
    # for Open-Elevation/OpenTopoData, whose practical batch limits are far smaller.
    elevation_batch_size: int = Field(default=1000, ge=1, le=2000)
    elevation_fallback_batch_size: int = Field(default=50, ge=1, le=200)
    elevation_max_retries: int = Field(default=1, ge=0, le=5)
    elevation_max_concurrent_requests: int = Field(default=12, ge=1, le=30)
    # Hard wall-clock cap on the whole fetch_elevations() call, regardless of
    # grid size or how many batches are still retrying — bounds worst case
    # to roughly this plus one in-flight request's timeout, instead of
    # scaling with (batch count / concurrency) unbounded. Keep comfortably
    # under the frontend's own request timeout.
    elevation_total_budget_s: float = Field(default=45.0, gt=0, le=300)

    # Fallback provider, tried only for points Open-Elevation could not
    # return (including total failure — e.g. its domain being unreachable
    # from a given network while other external APIs are fine).
    elevation_fallback_enabled: bool = True
    opentopodata_url: str = "https://api.opentopodata.org/v1/srtm90m"

    # ── Land-use constraint filter (buildings/roads/rivers/water bodies) ────
    # Keeps pond candidates off existing structures/water features. Failure
    # to reach Overpass just skips this filter for the analysis (plus a
    # warning) rather than blocking the core pipeline — same philosophy as
    # rainfall/elevation above.
    landuse_constraint_enabled: bool = True
    # The flagship overpass-api.de instance returned HTTP 406 (Apache/WAF-level
    # bot filtering, not an application error) from this development
    # environment's network — verified live, both GET and POST, with a
    # browser-like User-Agent. This mirror was verified to work instead;
    # override via .env if your deployment network reaches the flagship fine.
    overpass_url: str = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    overpass_request_timeout_s: float = Field(default=20.0, gt=0, le=60)
    overpass_max_retries: int = Field(default=1, ge=0, le=3)
    # Hard wall-clock cap on the whole _fetch_from_overpass call, regardless
    # of retry count — mirrors elevation_total_budget_s. Without this, two
    # independent 20s attempts is an open-ended ~40s worst case; a real
    # production log showed this stacking with elevation's own worst case
    # to approach the frontend's request timeout.
    overpass_total_budget_s: float = Field(default=25.0, gt=0, le=60)
    # Buffer distances (metres) — from the original spatial-constraint design.
    landuse_building_buffer_m: float = Field(default=100.0, ge=0)
    landuse_road_buffer_m: float = Field(default=50.0, ge=0)
    landuse_river_buffer_m: float = Field(default=30.0, ge=0)
    landuse_powerline_buffer_m: float = Field(default=75.0, ge=0)

    # ── Map-selected-area analysis limits ────────────────────────────────────
    # Bounds compute/API cost for a user-drawn polygon rather than a KML upload.
    selected_area_max_km2: float = Field(default=25.0, gt=0)
    selected_area_max_grid_points: int = Field(default=2500, ge=100)


# Singleton instance imported across the app
settings = Settings()

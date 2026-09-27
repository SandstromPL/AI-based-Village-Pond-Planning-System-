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
    app_debug: bool = True
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

    # ── External API Placeholders ───────────────────────────────────────────
    # [EXTERNAL_API_PLACEHOLDER: OpenZenith]
    openzenith_api_key: str = "PLACEHOLDER"
    openzenith_base_url: str = "https://api.openzenith.example/v1"

    # ── Open-Meteo rainfall ────────────────────────────────────────────────
    # Short-term rainfall forecast (up to 16 days). This is supplementary
    # information and is not used to size a pond.
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"

    # Historical rainfall for annual/monsoon water-volume estimation.
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    rainfall_history_start_year: int = Field(default=2015, ge=1900)
    # None means the most recently completed calendar year.
    rainfall_history_end_year: int | None = Field(default=None, ge=1900)
    rainfall_request_timeout_s: float = Field(default=10.0, gt=0, le=60)

    # [EXTERNAL_API_PLACEHOLDER: NASA POWER]
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"

    # [EXTERNAL_API_PLACEHOLDER: IMD]
    imd_api_key: str = "PLACEHOLDER"
    imd_base_url: str = "https://imdpune.gov.in/api"


# Singleton instance imported across the app
settings = Settings()

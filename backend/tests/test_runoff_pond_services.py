"""Unit tests for planning-level runoff and pond-sizing services."""

from app.models.rainfall import NormalizedRainfallData, RunoffResult
from app.services.pond_service import estimate_pond_size
from app.services.runoff_service import estimate_runoff


def test_estimate_runoff_uses_rainfall_area_and_coefficient():
    rainfall = NormalizedRainfallData(status="success", annual_avg_mm=1_000.0)

    result = estimate_runoff(rainfall, catchment_area_km2=0.05, runoff_coefficient=0.4)

    assert result.status == "success"
    assert result.runoff_coefficient == 0.4
    assert result.annual_runoff_m3 == 20_000.0


def test_estimate_runoff_is_unavailable_without_rainfall():
    result = estimate_runoff(NormalizedRainfallData(), catchment_area_km2=0.05)

    assert result.status == "unavailable"
    assert result.annual_runoff_m3 is None


def test_estimate_pond_size_calculates_storage_and_area():
    runoff = RunoffResult(status="success", annual_runoff_m3=12_000.0)

    result = estimate_pond_size(runoff, terrain_slope_deg=2.0)

    assert result.status == "success"
    assert result.recommended_depth_m == 3.0
    assert result.estimated_storage_m3 == 9_600.0
    assert result.estimated_surface_area_m2 == 3_200.0


def test_estimate_pond_size_uses_shallower_depth_on_steep_terrain():
    runoff = RunoffResult(status="success", annual_runoff_m3=12_000.0)

    result = estimate_pond_size(runoff, terrain_slope_deg=6.0)

    assert result.recommended_depth_m == 2.0
    assert result.estimated_surface_area_m2 == 4_800.0

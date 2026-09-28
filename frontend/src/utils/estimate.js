// Client-side Rational Method estimate, mirroring the backend's own
// formula (see backend/app/services/runoff_service.py) — applied per
// candidate using the single area-wide rainfall figure already in the
// response, not a location-specific one. Returns null if any input is
// missing (matches the safeNumber/safe fallback convention elsewhere).
export function estimateVolumeM3(catchmentAreaKm2, annualAvgMm, runoffCoefficient) {
  if (catchmentAreaKm2 == null || annualAvgMm == null || runoffCoefficient == null) return null
  const areaM2 = catchmentAreaKm2 * 1_000_000
  const rainfallM = annualAvgMm / 1000
  return areaM2 * rainfallM * runoffCoefficient
}

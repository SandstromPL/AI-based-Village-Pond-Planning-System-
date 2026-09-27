import { prettify, safe, safeNumber } from '../utils/format.js'

export default function ResultsPanel({ result }) {
  if (!result) {
    return (
      <div className="panel-card results-panel">
        <h2>Results</h2>
        <p className="panel-card__hint">
          Upload a contour map or draw an area on the map, then run an analysis to see results
          here.
        </p>
      </div>
    )
  }

  const recommended = result.recommended ?? null
  const rainfall = result.rainfall ?? {}
  const runoff = result.runoff ?? {}
  const pond = result.pond ?? {}
  const warnings = Array.isArray(result.warnings) ? result.warnings : []
  const candidates = Array.isArray(result.candidates) ? result.candidates : []

  return (
    <div className="results-panel">
      <div className={`status-banner status-banner--${safe(result.status, 'unknown')}`}>
        <strong>Status: {prettify(result.status)}</strong>
        <span>{safeNumber(result.processing_time_s, 2)}s processing time</span>
      </div>

      {warnings.length > 0 && (
        <div className="panel-card warnings-card">
          <h2>Warnings</h2>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="panel-card">
        <h2>Recommended Pond</h2>
        {recommended ? (
          <>
            <dl className="stat-grid">
              <div>
                <dt>Location</dt>
                <dd>
                  {safeNumber(recommended.location?.latitude, 5)},{' '}
                  {safeNumber(recommended.location?.longitude, 5)}
                </dd>
              </div>
              <div>
                <dt>Catchment area</dt>
                <dd>{safeNumber(recommended.catchment_area_km2, 4)} km²</dd>
              </div>
              <div className="stat-grid__highlight">
                <dt>Expected annual water volume</dt>
                <dd>{safeNumber(recommended.expected_annual_collection_m3, 0)} m³</dd>
              </div>
              <div>
                <dt>Planned storage</dt>
                <dd>{safeNumber(recommended.planned_storage_m3, 0)} m³</dd>
              </div>
              <div>
                <dt>Elevation</dt>
                <dd>{safeNumber(recommended.elevation_m, 1)} m</dd>
              </div>
              <div>
                <dt>Slope</dt>
                <dd>{safeNumber(recommended.slope_deg, 1)}°</dd>
              </div>
              <div>
                <dt>Score</dt>
                <dd>{safeNumber(recommended.score, 1)}</dd>
              </div>
            </dl>
            {Array.isArray(recommended.reasoning) && recommended.reasoning.length > 0 && (
              <ul className="reasoning-list">
                {recommended.reasoning.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="panel-card__hint">
            No candidate passed the terrain/catchment filters for this analysis.
          </p>
        )}
      </div>

      <div className="panel-card">
        <h2>Rainfall &amp; Runoff</h2>
        <dl className="stat-grid">
          <div>
            <dt>Rainfall status</dt>
            <dd>{prettify(rainfall.status)}</dd>
          </div>
          <div>
            <dt>Annual average rainfall</dt>
            <dd>{safeNumber(rainfall.annual_avg_mm, 1)} mm</dd>
          </div>
          <div>
            <dt>Runoff coefficient</dt>
            <dd>{safeNumber(runoff.runoff_coefficient, 2)}</dd>
          </div>
          <div>
            <dt>Annual runoff</dt>
            <dd>{safeNumber(runoff.annual_runoff_m3, 0)} m³</dd>
          </div>
          <div>
            <dt>Pond depth</dt>
            <dd>{safeNumber(pond.recommended_depth_m, 1)} m</dd>
          </div>
          <div>
            <dt>Pond surface area</dt>
            <dd>{safeNumber(pond.estimated_surface_area_m2, 0)} m²</dd>
          </div>
        </dl>
      </div>

      <details className="panel-card">
        <summary>Terrain statistics</summary>
        <dl className="stat-grid">
          <div>
            <dt>Elevation range</dt>
            <dd>
              {safeNumber(result.terrain?.min_elevation_m, 1)} –{' '}
              {safeNumber(result.terrain?.max_elevation_m, 1)} m
            </dd>
          </div>
          <div>
            <dt>Average slope</dt>
            <dd>{safeNumber(result.terrain?.avg_slope_deg, 1)}°</dd>
          </div>
          <div>
            <dt>DEM resolution</dt>
            <dd>{safeNumber(result.terrain?.dem_resolution_m, 0)} m</dd>
          </div>
          <div>
            <dt>Grid size</dt>
            <dd>
              {safe(result.terrain?.grid_rows)} × {safe(result.terrain?.grid_cols)}
            </dd>
          </div>
        </dl>
      </details>

      <details className="panel-card">
        <summary>All candidates ({candidates.length})</summary>
        {candidates.length === 0 ? (
          <p className="panel-card__hint">No candidates were generated.</p>
        ) : (
          <table className="candidates-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Score</th>
                <th>Catchment (km²)</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id}>
                  <td>{safe(c.id)}</td>
                  <td>{prettify(c.status)}</td>
                  <td>{safeNumber(c.score, 1)}</td>
                  <td>{safeNumber(c.catchment_area_km2, 4)}</td>
                  <td>{c.rejection_reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
    </div>
  )
}

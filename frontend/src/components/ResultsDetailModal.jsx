import { useEffect } from 'react'
import { prettify, safe, safeNumber } from '../utils/format.js'
import { estimateVolumeM3 } from '../utils/estimate.js'

const MONTH_ORDER = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const SCORE_BREAKDOWN_FIELDS = [
  ['catchment_score', 'Catchment'],
  ['flow_score', 'Flow accumulation'],
  ['slope_score', 'Slope'],
  ['relief_score', 'Relief'],
  ['depression_score', 'Depression'],
  ['final_score', 'Final (weighted)'],
]

const ASSUMPTION_FIELDS = [
  ['dem_resolution_m', 'DEM resolution (m)'],
  ['dem_interp_method', 'DEM interpolation method'],
  ['max_slope_filter_deg', 'Max slope filter (°)'],
  ['flow_acc_threshold_percentile', 'Flow-accumulation percentile threshold'],
  ['min_candidate_distance_m', 'Min candidate distance (m)'],
  ['min_catchment_km2', 'Min catchment (km²)'],
  ['max_candidates', 'Max candidates returned'],
  ['rainfall_source', 'Rainfall source'],
  ['runoff_coefficient', 'Runoff coefficient'],
]

export default function ResultsDetailModal({ result, onClose }) {
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const recommended = result.recommended ?? null
  const rainfall = result.rainfall ?? {}
  const runoff = result.runoff ?? {}
  const assumptions = result.assumptions ?? {}
  const candidates = Array.isArray(result.candidates) ? result.candidates : []
  // RecommendedSchema (the backend response shape) doesn't carry its own
  // score_breakdown — only CandidateSchema does. Look it up from the full
  // candidates list by matching candidate_id, rather than assuming it's on
  // `recommended` directly.
  const recommendedScoreBreakdown = recommended
    ? candidates.find((c) => c.id === recommended.candidate_id)?.score_breakdown ?? null
    : null
  const monthlyAvgMm = rainfall.monthly_avg_mm ?? {}
  const scoreWeights = assumptions.score_weights ?? {}

  function handleOverlayClick(event) {
    if (event.target === event.currentTarget) onClose()
  }

  return (
    <div className="results-modal-overlay" onClick={handleOverlayClick}>
      <div className="results-modal" role="dialog" aria-modal="true" aria-label="Full analysis details">
        <div className="results-modal__header">
          <h2>Full Analysis Details</h2>
          <button type="button" className="results-modal__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="results-modal__body">
          <section className="panel-card">
            <h3>Recommended Pond — Score Breakdown</h3>
            {recommended ? (
              <>
                {recommendedScoreBreakdown ? (
                  <dl className="stat-grid">
                    {SCORE_BREAKDOWN_FIELDS.map(([key, label]) => (
                      <div key={key}>
                        <dt>{label}</dt>
                        <dd>{safeNumber(recommendedScoreBreakdown[key], 1)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="panel-card__hint">Score breakdown unavailable for this candidate.</p>
                )}
                {Array.isArray(recommended.reasoning) && recommended.reasoning.length > 0 && (
                  <ul className="reasoning-list">
                    {recommended.reasoning.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <p className="panel-card__hint">No recommended candidate for this analysis.</p>
            )}
          </section>

          <section className="panel-card">
            <h3>Rainfall — Monthly Detail</h3>
            <p className="panel-card__hint">Source: {safe(rainfall.source)}</p>
            <table className="candidates-table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Avg. precipitation (mm)</th>
                </tr>
              </thead>
              <tbody>
                {MONTH_ORDER.map((month) => (
                  <tr key={month}>
                    <td>{month}</td>
                    <td>{safeNumber(monthlyAvgMm[month], 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="panel-card__hint">
              Monsoon (Jun–Sep) average: {safeNumber(rainfall.seasonal_mm?.monsoon_jun_sep_avg_mm, 1)} mm
            </p>
          </section>

          <section className="panel-card">
            <h3>All Candidates — Expanded</h3>
            <p className="panel-card__hint">
              Expected Volume is estimated per candidate from its own catchment area using the
              area-wide rainfall average above — not a location-specific rainfall figure.
            </p>
            {candidates.length === 0 ? (
              <p className="panel-card__hint">No candidates were generated.</p>
            ) : (
              <div className="results-modal__table-scroll">
                <table className="candidates-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Status</th>
                      <th>Seed Type</th>
                      <th>Score</th>
                      <th>Elevation (m)</th>
                      <th>Slope (°)</th>
                      <th>Catchment (km²)</th>
                      <th>Expected Volume (m³)</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.id}>
                        <td>{safe(c.id)}</td>
                        <td>{prettify(c.status)}</td>
                        <td>{prettify(c.seed_type)}</td>
                        <td>{safeNumber(c.score, 1)}</td>
                        <td>{safeNumber(c.elevation_m, 1)}</td>
                        <td>{safeNumber(c.slope_deg, 1)}</td>
                        <td>{safeNumber(c.catchment_area_km2, 4)}</td>
                        <td>
                          {safeNumber(
                            estimateVolumeM3(
                              c.catchment_area_km2,
                              rainfall.annual_avg_mm,
                              runoff.runoff_coefficient,
                            ),
                            0,
                          )}
                        </td>
                        <td>{c.rejection_reason || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel-card">
            <h3>Assumptions</h3>
            <dl className="stat-grid">
              {ASSUMPTION_FIELDS.map(([key, label]) => (
                <div key={key}>
                  <dt>{label}</dt>
                  <dd>{safe(assumptions[key])}</dd>
                </div>
              ))}
            </dl>
            {Object.keys(scoreWeights).length > 0 && (
              <>
                <h4>Score weights</h4>
                <dl className="stat-grid">
                  {Object.entries(scoreWeights).map(([key, value]) => (
                    <div key={key}>
                      <dt>{prettify(key)}</dt>
                      <dd>{safeNumber(value, 2)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

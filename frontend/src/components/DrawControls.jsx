export default function DrawControls({ hasSelection, areaKm2, onAnalyze, onClear, busy }) {
  return (
    <div className="panel-card">
      <h2>Draw an area on the map</h2>
      <p className="panel-card__hint">
        Use the rectangle or polygon tool in the map's top-right corner to draw the land area
        you want analyzed.
      </p>

      {hasSelection ? (
        <p className="panel-card__hint">Selected area: ~{areaKm2?.toFixed(2) ?? '—'} km²</p>
      ) : (
        <p className="panel-card__hint">No area drawn yet.</p>
      )}

      <div className="panel-card__actions">
        <button
          type="button"
          className="primary-button"
          onClick={onAnalyze}
          disabled={busy || !hasSelection}
        >
          {busy ? 'Analyzing…' : 'Analyze Selected Area'}
        </button>
        <button
          type="button"
          className="ghost-button"
          onClick={onClear}
          disabled={busy || !hasSelection}
        >
          Clear
        </button>
      </div>
    </div>
  )
}

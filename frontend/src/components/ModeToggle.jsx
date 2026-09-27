export default function ModeToggle({ mode, onChange, disabled }) {
  return (
    <div className="mode-toggle" role="tablist" aria-label="Input mode">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'upload'}
        className={mode === 'upload' ? 'is-active' : ''}
        onClick={() => onChange('upload')}
        disabled={disabled}
      >
        Upload KML/KMZ
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'draw'}
        className={mode === 'draw' ? 'is-active' : ''}
        onClick={() => onChange('draw')}
        disabled={disabled}
      >
        Draw Area on Map
      </button>
    </div>
  )
}

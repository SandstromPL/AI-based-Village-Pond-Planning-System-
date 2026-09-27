import { useRef, useState } from 'react'

export default function UploadPanel({ onAnalyze, busy }) {
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState('')

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    setFileName(file ? file.name : '')
  }

  function handleSubmit(event) {
    event.preventDefault()
    const file = inputRef.current?.files?.[0]
    if (file) onAnalyze(file)
  }

  return (
    <form className="panel-card" onSubmit={handleSubmit}>
      <h2>Upload a contour map</h2>
      <p className="panel-card__hint">Accepts a .kml or .kmz contour file.</p>
      <input
        ref={inputRef}
        type="file"
        accept=".kml,.kmz"
        onChange={handleFileChange}
        disabled={busy}
      />
      <button type="submit" className="primary-button" disabled={busy || !fileName}>
        {busy ? 'Analyzing…' : 'Analyze Contour Map'}
      </button>
    </form>
  )
}

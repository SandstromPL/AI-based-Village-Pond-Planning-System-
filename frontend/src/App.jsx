import { useCallback, useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet-draw'
import Header from './components/Header.jsx'
import ModeToggle from './components/ModeToggle.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import DrawControls from './components/DrawControls.jsx'
import MapView from './components/MapView.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import LoadingOverlay from './components/LoadingOverlay.jsx'
import ErrorBanner from './components/ErrorBanner.jsx'
import { analyzeArea, analyzeContour, ApiError } from './api.js'
import { useTheme } from './theme.js'

const SIDEBAR_MIN_WIDTH = 260
const SIDEBAR_MAX_WIDTH = 640
const SIDEBAR_DEFAULT_WIDTH = 340

function readStoredSidebarWidth() {
  try {
    const stored = Number(localStorage.getItem('sidebarWidth'))
    if (stored >= SIDEBAR_MIN_WIDTH && stored <= SIDEBAR_MAX_WIDTH) return stored
  } catch {
    // Private browsing / blocked storage — fall back to the default.
  }
  return SIDEBAR_DEFAULT_WIDTH
}

export default function App() {
  const { theme, toggleTheme } = useTheme()

  const [mode, setMode] = useState('upload')
  const [busy, setBusy] = useState(false)
  const [busyMessage, setBusyMessage] = useState('')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const [drawnPolygon, setDrawnPolygon] = useState(null) // [[lon, lat], ...]
  const [drawnAreaKm2, setDrawnAreaKm2] = useState(null)
  const [clearSignal, setClearSignal] = useState(0)

  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth)
  const resizingRef = useRef(false)

  const handleResizerPointerDown = useCallback((event) => {
    event.preventDefault()
    resizingRef.current = true
    document.body.classList.add('is-resizing-sidebar')
  }, [])

  useEffect(() => {
    function handlePointerMove(event) {
      if (!resizingRef.current) return
      const next = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, event.clientX))
      setSidebarWidth(next)
    }

    function stopResizing() {
      if (!resizingRef.current) return
      resizingRef.current = false
      document.body.classList.remove('is-resizing-sidebar')
      setSidebarWidth((current) => {
        try {
          localStorage.setItem('sidebarWidth', String(current))
        } catch {
          // Not essential — the width just won't persist across reloads.
        }
        return current
      })
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResizing)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResizing)
    }
  }, [])

  // Switching modes starts a new analysis — clear the previous one's
  // results/drawing so the map and results panel don't show stale state
  // while the user sets up the next input (previously the only way to get
  // a clean slate was reloading the whole page).
  const handleModeChange = useCallback((newMode) => {
    setMode(newMode)
    setError(null)
    setResult(null)
    setDrawnPolygon(null)
    setDrawnAreaKm2(null)
    setClearSignal((n) => n + 1)
  }, [])

  const handleAreaDrawn = useCallback((latlngs) => {
    // Leaflet gives {lat, lng}; the backend's polygon expects [lon, lat]
    // (GeoJSON coordinate order) — this swap is the one easy-to-miss step.
    const polygon = latlngs.map((ll) => [ll.lng, ll.lat])
    setDrawnPolygon(polygon)
    try {
      setDrawnAreaKm2(L.GeometryUtil.geodesicArea(latlngs) / 1_000_000)
    } catch {
      setDrawnAreaKm2(null)
    }
  }, [])

  const handleAreaCleared = useCallback(() => {
    setDrawnPolygon(null)
    setDrawnAreaKm2(null)
  }, [])

  const handleClearDrawing = useCallback(() => {
    setDrawnPolygon(null)
    setDrawnAreaKm2(null)
    setClearSignal((n) => n + 1)
  }, [])

  async function handleAnalyzeContour(file) {
    setBusy(true)
    setBusyMessage('Parsing contour file and analyzing terrain…')
    setError(null)
    try {
      const data = await analyzeContour(file)
      setResult(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  async function handleAnalyzeArea() {
    if (!drawnPolygon) return
    setBusy(true)
    setBusyMessage(
      'Fetching elevation data and analyzing terrain… this can take up to a couple of minutes for a freshly-drawn area, especially the first time.',
    )
    setError(null)
    try {
      const data = await analyzeArea(drawnPolygon)
      setResult(data)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-shell">
      <Header theme={theme} onToggleTheme={toggleTheme} />

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <main className="app-main">
        <div className="sidebar" style={{ '--sidebar-width': `${sidebarWidth}px` }}>
          <ModeToggle mode={mode} onChange={handleModeChange} disabled={busy} />

          {mode === 'upload' ? (
            <UploadPanel onAnalyze={handleAnalyzeContour} busy={busy} />
          ) : (
            <DrawControls
              hasSelection={Boolean(drawnPolygon)}
              areaKm2={drawnAreaKm2}
              onAnalyze={handleAnalyzeArea}
              onClear={handleClearDrawing}
              busy={busy}
            />
          )}

          <ResultsPanel result={result} />
        </div>

        <div
          className="sidebar-resizer"
          onPointerDown={handleResizerPointerDown}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
        />

        <div className="map-container">
          <MapView
            theme={theme}
            result={result}
            mode={mode}
            onAreaDrawn={handleAreaDrawn}
            onAreaCleared={handleAreaCleared}
            clearSignal={clearSignal}
          />
          {busy && <LoadingOverlay message={busyMessage} />}
        </div>
      </main>
    </div>
  )
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(
  /\/+$/,
  '',
)
// The backend's real-world worst case, measured from production logs, runs
// closer to ~90-100s than the old ~70-75s estimate: elevation's 45s budget
// can overshoot to ~65s (an in-flight request already launched before its
// deadline can't be aborted mid-socket-call), plus land-use's now-bounded
// ~25s (overlapped with elevation, not purely additive) plus rainfall's
// ~10s. This stays comfortably above that so the frontend doesn't give up
// on a request the backend would have finished. If this ever fires, the
// backend really did exceed its own budget.
const DEFAULT_TIMEOUT_MS = 155_000

export class ApiError extends Error {
  constructor(status, detail, analysisId) {
    super(detail || `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.analysisId = analysisId ?? null
  }
}

function extractDetail(body) {
  if (!body || body.detail === undefined) return null
  // FastAPI's own validation errors (422) are a list of {msg, loc, ...};
  // our custom handler's shape is a plain string — handle both.
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => d?.msg || JSON.stringify(d)).join('; ')
  }
  return String(body.detail)
}

async function handleResponse(res) {
  let body = null
  try {
    body = await res.json()
  } catch {
    // Non-JSON or empty body — fall through with body left as null.
  }

  if (!res.ok) {
    const detail = extractDetail(body) || `Request failed with status ${res.status}`
    throw new ApiError(res.status, detail, body?.analysis_id)
  }

  return body
}

async function requestWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    return await handleResponse(res)
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err?.name === 'AbortError') {
      throw new ApiError(
        0,
        'The request took too long and was cancelled. The server may still be processing it in the background — please try again shortly.',
      )
    }
    throw new ApiError(
      0,
      'Could not reach the server. Check your connection and the backend URL configuration.',
    )
  } finally {
    clearTimeout(timeoutId)
  }
}

export function analyzeContour(file) {
  const formData = new FormData()
  formData.append('contour_map', file)
  return requestWithTimeout(`${API_BASE}/analyzeContour`, {
    method: 'POST',
    body: formData,
  })
}

export function analyzeArea(polygonLonLat, resolutionM) {
  const payload = { polygon: polygonLonLat }
  if (resolutionM) payload.resolution_m = resolutionM
  return requestWithTimeout(`${API_BASE}/analyzeArea`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getAnalysis(analysisId) {
  return requestWithTimeout(`${API_BASE}/analysis/${analysisId}`, { method: 'GET' })
}

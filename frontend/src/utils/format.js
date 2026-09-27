// Small display helpers used throughout ResultsPanel. Every value coming
// from the API is treated as possibly missing (many backend fields are
// Optional) — these never throw on null/undefined, they just fall back.

export function safe(value, fallback = '—') {
  if (value === null || value === undefined || value === '') return fallback
  return value
}

export function safeNumber(value, digits = 2, fallback = '—') {
  if (value === null || value === undefined) return fallback
  const num = Number(value)
  if (Number.isNaN(num)) return fallback
  return num.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

// Turns any snake_case status/reason string into a readable label without
// a hardcoded lookup table, so a brand-new value the frontend has never
// seen (e.g. a future "rejected_constraint_building_buffer") still
// displays sensibly instead of rendering blank.
export function prettify(value) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
    .replace(/^rejected_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

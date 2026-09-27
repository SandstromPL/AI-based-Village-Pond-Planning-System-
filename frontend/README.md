# Village Pond Planner — Frontend

> **AI-based Village Pond Planning System** | CSD Assignment 1 | Phase 3 Frontend

A small React + Vite + Leaflet app: select a land area on a map (or upload a
KML/KMZ contour file), run an analysis against the backend, and see the
recommended pond location, catchment area, and expected water volume
overlaid on the map.

Deliberately lightweight — no state-management library, no UI framework, no
TypeScript. Plain CSS with theme variables (dark by default, light switch),
`useState`/`useReducer` for state, and a handful of small components.

---

## Quick Start

```bash
npm install
cp .env.example .env
# Edit .env to point at your backend, e.g.:
#   VITE_API_BASE_URL=http://localhost:8000/api/v1

npm run dev       # http://localhost:5173
```

## Build for deployment

```bash
npm run build     # outputs static files to dist/
```

`dist/` is a fully static site — serve it with any static file server
(nginx, `serve`, etc.) pointed at a backend reachable at the URL baked in
from `VITE_API_BASE_URL` at build time. This project is deployed
independently from the backend (CORS on the backend already allows this).

## Project layout

```
src/
  main.jsx, App.jsx        — entry point, top-level layout/state
  api.js                   — fetch wrappers + error normalization
  theme.js                 — dark/light theme (localStorage-persisted)
  components/
    Header.jsx              — title + theme switch
    ModeToggle.jsx           — "Upload KML/KMZ" vs "Draw Area" tabs
    UploadPanel.jsx          — file input → POST /analyzeContour
    DrawControls.jsx         — draw-area instructions + analyze/clear buttons
    MapView.jsx              — Leaflet map: base layers, leaflet-draw
                                integration, GeoJSON overlay rendering
    ResultsPanel.jsx         — status/warnings + recommended/rainfall/
                                runoff/pond stat cards + candidates table
    LoadingOverlay.jsx, ErrorBanner.jsx
  utils/
    format.js                — safe/prettify display helpers (never crash
                                on a null/unknown value from the API)
    geojson.js                — strips invalid/null-geometry GeoJSON
                                features before rendering
```

## Notes on choices made

- **Map tiles**: standard OpenStreetMap tiles for both themes (dark is a CSS
  filter on the same tiles, not a different tile source) plus an Esri
  World Imagery satellite option. Esri's "Canvas" dark/light basemaps were
  tried first but have real coverage gaps in rural areas — confirmed by
  actually loading a rural test location and finding real
  "Map data not yet available" placeholder tiles, not just a styling issue.
- **`leaflet-draw` is pinned to `1.0.2`**, not the latest `1.0.4` — a bug in
  1.0.3/1.0.4's rectangle area-measurement code throws `type is not defined`
  under strict-mode ESM bundlers like Vite (harmless in practice, but noisy
  and worth avoiding). See [Leaflet/Leaflet.draw#1026](https://github.com/Leaflet/Leaflet.draw/issues/1026).
- **No test framework** — verification for this scope is manual (see the
  project's plan notes) plus a one-off Playwright smoke pass during
  development; adding Vitest/RTL was judged not worth the extra tooling for
  a UI this size.

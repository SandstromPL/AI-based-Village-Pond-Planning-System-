# AI-based Village Pond Planning System

> CSD Assignment 1 — Final Submission
> **Paritosh Lahre** (Student ID: 12341550), Indian Institute of Technology Bhilai

A full-stack decision-support system that recommends pond/check-dam
locations from either an uploaded contour map (KML/KMZ) or a user-drawn
area on an interactive map. It reconstructs terrain, analyzes drainage,
scores candidate sites, filters out sites that conflict with existing
buildings/roads/rivers, estimates expected water volume from real
historical rainfall, and presents all of it overlaid on a map — engineered
to keep working (with honest warnings) when any of its external data
sources is temporarily unavailable, which in practice is often.

- **Report**: [`report.pdf`](./report.pdf) / [`report.tex`](./report.tex) (ACM format, 10 pages)
- **Backend docs**: [`backend/README.md`](./backend/README.md) — full API reference, configuration, algorithms
- **Frontend docs**: [`frontend/README.md`](./frontend/README.md)
- **Deployed frontend**: _TODO_
- **Demo video**: _TODO_

---

## What it does

Two input modes, one pipeline:

```
KML/KMZ Upload                          Map-drawn Polygon
    ↓                                        ↓
Contour parsing → DEM interpolation    Copernicus DEM tile read, falling
                                        back to OpenZenith → Open-Elevation
                                        → OpenTopoData if unavailable
    └───────────────────┬────────────────────┘
                         ↓
    Priority-Flood depression filling → D8 flow direction → flow
    accumulation → candidate generation → hard filters (slope, catchment
    size, land-use constraint via live OpenStreetMap data) → catchment
    delineation → multi-factor scoring
                         ↓
    Historical rainfall (Open-Meteo) → Rational-Method runoff estimate
    → planning-level pond sizing (depth, surface area, storage volume)
                         ↓
    Structured JSON + GeoJSON layers, rendered on an interactive map
```

Results include the recommended pond's location, its catchment area,
expected annual collectable water volume, and planned storage — plus,
in the frontend's "View Full Details" modal, a per-candidate score
breakdown, monthly rainfall detail, and every assumption/parameter the
analysis used.

## Why this is more resilient than it sounds

Every external data source this project depends on (three elevation
providers, one land-use provider, one rainfall provider) is free,
community- or hobby-run infrastructure with no uptime guarantee — and
during development, every single one of them failed for real: DNS
resolution errors, confirmed rate-limiting, connection resets, bot
filtering. Rather than treat that as an edge case, the whole backend is
built around it:

- **Bounded timeouts + sensible retries** — a slow/overloaded server gets
  retried once; a broken DNS/connection does not, since a same-second
  retry of that essentially never succeeds (confirmed from real
  production logs — retrying anyway was doubling failure time for no
  benefit).
- **Multi-tier fallback** — elevation tries a static, non-rate-limited
  data source (Copernicus DEM GLO-30, read directly from public AWS S3
  storage) before falling through a 3-provider REST cascade
  (OpenZenith → Open-Elevation → OpenTopoData).
- **A shared circuit breaker** — once a provider is seen rate-limited or
  unreachable, further requests skip it immediately for a cooldown window
  instead of re-discovering the same failure from scratch every time.
- **Graceful degradation everywhere** — a failed rainfall or land-use
  fetch never fails the whole request; the response comes back with an
  explicit `"unavailable"` status and a warning, and the rest of the
  analysis still completes.

See `report.pdf` §8 (Discussion and Limitations) and `report.md` for the
full, evidence-based account of what actually broke and how it was fixed.

---

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at `http://localhost:8000/docs`. See
[`backend/README.md`](./backend/README.md) for the full endpoint
reference, every configuration variable, and the algorithms used.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# point VITE_API_BASE_URL at your backend, e.g. http://localhost:8000/api/v1
npm run dev       # http://localhost:5173
```

### Tests

```bash
cd backend
pytest tests/ -v   # 70 tests
```

---

## Repository structure

```
backend/
  app/
    api/          — HTTP route handlers
    services/      — pipeline orchestration (one service per concern)
    algorithms/    — pure computation (depression fill, D8 flow, flow
                     accumulation, watershed, scoring, slope, interpolation)
    providers/      — external API integrations (elevation, land-use)
    models/        — dataclasses + Pydantic schemas
    utils/         — geo helpers, GeoJSON, in-memory storage, circuit
                     breaker, shared HTTP client identity
  tests/           — 70 pytest tests
frontend/
  src/
    components/    — map view, results panel + detail modal, upload/draw
                     controls, loading/error UI
    utils/         — display formatting, GeoJSON filtering, volume estimate
    api.js, theme.js, App.jsx
report.tex / report.pdf   — final technical report
report.md                 — working notes (session-by-session build log)
video_script.md            — demo video script
```

## Tech stack

**Backend**: Python, FastAPI, Pydantic, GeoPandas, Shapely, pyproj,
rasterio, NumPy, SciPy, httpx. **Frontend**: React 19, Vite, Leaflet +
react-leaflet + leaflet-draw, plain CSS (no state library, no
TypeScript, no UI framework). **External data**: Copernicus DEM (AWS S3
Open Data), OpenZenith, Open-Elevation, OpenTopoData, Overpass API
(OpenStreetMap), Open-Meteo — all free, no API key required.

## AI tool usage

Claude (Anthropic's Claude Code CLI) assisted with implementation,
debugging, and report drafting; all changes were reviewed and tested by
the author.

# Village Pond Planning API — Phase 3

> **AI-based Village Pond Planning System** | CSD Assignment 1 | Phase 3 Backend

A FastAPI backend that analyzes terrain and hydrology and recommends suitable pond
locations, catchment areas, and expected collectable water volume — from either
an uploaded contour map (KML/KMZ) or a user-drawn map area.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the sample KML to the data directory
cp ../input/contours_1m.kml data/

# 4. Copy and configure environment
cp .env.example .env
# Edit .env if you want to change DEM resolution, thresholds, or API limits

# 5. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the interactive API docs (Swagger UI).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyzeContour` | Upload KML/KMZ → full analysis |
| `POST` | `/api/v1/analyzeArea` | Submit a map-drawn polygon → full analysis (no file) |
| `GET`  | `/api/v1/analysis/{id}` | Retrieve a previous analysis |
| `GET`  | `/api/v1/health` | Service health check |

Both analysis endpoints return the same response shape (`AnalysisResponse`):
terrain stats, ranked candidates, the recommended pond (location, catchment,
**expected annual water collection, planned storage**), rainfall/runoff/pond
detail, and frontend-ready GeoJSON layers.

### Example: Analyze a contour map

```bash
curl -X POST http://localhost:8000/api/v1/analyzeContour \
  -F "contour_map=@data/contours_1m.kml" | python3 -m json.tool | head -80
```

### Example: Analyze a map-selected area

```bash
curl -X POST http://localhost:8000/api/v1/analyzeArea \
  -H "Content-Type: application/json" \
  -d '{
        "polygon": [
          [81.2798, 21.2602], [81.2858, 21.2602],
          [81.2858, 21.2662], [81.2798, 21.2662]
        ]
      }' | python3 -m json.tool | head -80
```

`polygon` is a ring of `[longitude, latitude]` pairs (GeoJSON order), at least
3 points — typically a rectangle drawn on the frontend map. There's no KML
file in this path: elevation for a grid sampled over the polygon's bounding
box is fetched live from OpenZenith (falling back to Open-Elevation, then
OpenTopoData, for any points it couldn't provide), then fed into the same
terrain pipeline as the contour-upload flow.

---

## Analysis Pipeline

```
KML/KMZ Upload                          Map-drawn Polygon
    ↓                                        ↓
File Validation & Parsing            Bounding box + size/grid-point caps
    ↓                                        ↓
DEM via contour interpolation        DEM via Copernicus DEM tile reads
    │                                        │ (OpenZenith/Open-Elevation/
    │                                        │  OpenTopoData fallback,
    │                                        │  nearest-neighbour gap fill)
    └───────────────────┬────────────────────┘
                         ↓
        Hydrological Conditioning (Priority-Flood depression fill)
                         ↓
        D8 Flow Direction (steepest downhill neighbour)
                         ↓
        Flow Accumulation (topological sort)
                         ↓
        Candidate Generation
           ├── Depression seeds (genuine terrain bowls)
           └── Flow convergence seeds (high accumulation points)
                         ↓
        Hard Filters (slope, catchment size, land-use constraint)
                         ↓
        Catchment Delineation (upstream BFS per candidate)
                         ↓
        Multi-factor Scoring & Ranking
                         ↓
        Historical Rainfall (Open-Meteo, cached, graceful degradation)
                         ↓
        Runoff Estimation (Rational Method: C × rainfall × catchment area)
                         ↓
        Pond Sizing (storage = runoff × retention factor; depth by slope)
                         ↓
        Structured JSON + GeoJSON layers (incl. expected water volume)
```

If rainfall or elevation data is temporarily unavailable, the pipeline still
completes — the response reports `status: "unavailable"` on the affected
section with a clear message, plus a top-level warning, instead of failing
the whole request.

---

## Configuration

All parameters are in `.env` (see `.env.example`):

### Cross-cutting resilience

| Variable | Default | Description |
|---|---|---|
| `CIRCUIT_BREAKER_COOLDOWN_S` | `60` | Shared by all four external-provider fetch functions (OpenZenith, Open-Elevation, OpenTopoData, Overpass). After a provider is seen rate-limited (HTTP 429/503) or unreachable, further requests skip it immediately for this long instead of a brand-new request re-discovering the same failure from scratch every time |

### Terrain & candidate generation

| Variable | Default | Description |
|---|---|---|
| `DEM_RESOLUTION_M` | `30` | DEM grid cell size (metres) |
| `DEM_BBOX_PADDING_FRAC` | `0.1` | Grid padding beyond the contour/selected-area bounding box on each side (avoids flow-routing edge artifacts). For `/analyzeArea`, a candidate can otherwise land in this padding margin, outside the polygon the user drew — see the next row |
| `MAX_SLOPE_DEG` | `15` | Hard filter: reject candidates with slope > this |
| `MIN_CATCHMENT_KM2` | `0.005` | Hard filter: reject if catchment < this |
| *(no setting — always on for `/analyzeArea`)* | — | Hard filter: reject a candidate (`rejected_outside_selection`) whose point falls outside the polygon the user actually drew, even though it's inside the padded DEM grid. Catchment *boundaries* are left unrestricted — a real drainage basin isn't bounded by an arbitrary polygon. Not applied to contour uploads (no narrower user-drawn shape to restrict to there) |
| `MAX_CANDIDATES` | `5` | Maximum candidates to return |
| `FLOW_ACC_PERCENTILE` | `99` | Top percentile for flow-convergence seeds |
| `MIN_CANDIDATE_DISTANCE_M` | `100` | Minimum separation between candidates |

### Rainfall, runoff, pond sizing

| Variable | Default | Description |
|---|---|---|
| `OPEN_METEO_ARCHIVE_URL` | Open-Meteo `/v1/archive` | Historical daily precipitation source |
| `RAINFALL_HISTORY_START_YEAR` | `2015` | First year of the historical window |
| `RAINFALL_HISTORY_END_YEAR` | last complete year | Last year of the historical window |
| `RUNOFF_COEFFICIENT_DEFAULT` | `0.35` | Rational Method `C` (mixed agricultural/semi-pervious land) |
| `POND_RETENTION_FACTOR` | `0.80` | Fraction of annual runoff assumed captured |
| `POND_DEFAULT_DEPTH_M` / `POND_STEEP_SLOPE_DEPTH_M` | `3.0` / `2.0` | Indicative pond depth, shallower on steep terrain |

### Map-selected-area analysis (`/analyzeArea`)

| Variable | Default | Description |
|---|---|---|
| `COPERNICUS_DEM_ENABLED` | `true` | Tried first: reads Copernicus DEM GLO-30 directly as static COG tiles from public AWS S3 storage — a file read, not a rate-limited API call, so there's no per-request quota to exhaust |
| `COPERNICUS_DEM_BUCKET_URL` / `COPERNICUS_DEM_REQUEST_TIMEOUT_S` | S3 Open Data bucket / `15` | Bucket base URL and GDAL HTTP timeout for opening/reading a tile |
| `OPENZENITH_URL` | `https://openzenith.org` | Fallback tier 1 — handles up to 2000 points/request, no API key |
| `OPENZENITH_REQUEST_TIMEOUT_S` / `OPENZENITH_MAX_RETRIES` | `15` / `1` | Kept tight relative to the 45s total budget so one failing batch can't consume it all before the fallback chain gets a turn |
| `ELEVATION_BATCH_SIZE` | `1000` | Outer batch size, sized for OpenZenith's large per-request limit |
| `ELEVATION_FALLBACK_BATCH_SIZE` | `50` | Sub-batch size when re-chunking OpenZenith's leftovers for Open-Elevation/OpenTopoData |
| `ELEVATION_MAX_RETRIES` | `1` | Retries per batch before giving up (fallback providers) |
| `ELEVATION_MAX_CONCURRENT_REQUESTS` | `12` | Batches fetched in parallel (bounds wall-clock time) |
| `ELEVATION_TOTAL_BUDGET_S` | `45` | Hard wall-clock cap on the whole elevation fetch — bounds worst case regardless of grid size or how badly the providers are behaving |
| `OPEN_ELEVATION_URL` | Open-Elevation public API | First fallback — only used for points OpenZenith couldn't provide |
| `ELEVATION_FALLBACK_ENABLED` / `OPENTOPODATA_URL` | `true` / OpenTopoData public API | Second fallback — only used for points neither OpenZenith nor Open-Elevation could return. Calls to it are serialized to at most 1/second across all concurrent batches (its documented public-server limit), regardless of `ELEVATION_MAX_CONCURRENT_REQUESTS` |
| `SELECTED_AREA_MAX_KM2` | `25` | Reject polygons larger than this |
| `SELECTED_AREA_MAX_GRID_POINTS` | `2500` | Auto-coarsen DEM resolution above this many cells |

A point that fails every provider tier is **not** cached — only a real
elevation value is. A permanent process-lifetime cache of failures was a
real production bug: once one bad network episode failed a point, every
later request for that same area was served the cached failure forever,
even after the network recovered. Now a later request simply retries it.

### Land-use constraint filter (buildings/roads/rivers/water bodies)

| Variable | Default | Description |
|---|---|---|
| `LANDUSE_CONSTRAINT_ENABLED` | `true` | Reject candidates that fall on/near an existing building, road, waterway, water body, or power line |
| `OVERPASS_URL` | `overpass.openstreetmap.fr` (a recognized community-run instance) | OSM data source for exclusion geometries. A prior default, `maps.mail.ru`, was found to be an unaffiliated third-party proxy — not listed on OSM's own Overpass status page — and measured at 13-15s/request; this one was live-tested faster/working |
| `OVERPASS_REQUEST_TIMEOUT_S` / `OVERPASS_MAX_RETRIES` | `20` / `1` | Bounded like every other external call — failure skips the filter (plus a warning), never blocks the analysis |
| `OVERPASS_TOTAL_BUDGET_S` | `25` | Hard wall-clock cap on the whole Overpass fetch regardless of retry count — mirrors `ELEVATION_TOTAL_BUDGET_S`. Without it, two full-timeout attempts is an open-ended ~40s worst case that can stack with elevation's own worst case and approach the frontend's request timeout |
| `LANDUSE_BUILDING_BUFFER_M` / `_ROAD_` / `_RIVER_` / `_POWERLINE_` | `100` / `50` / `30` / `75` | Buffer distance (metres) around each feature type |

For `/analyzeArea`, the Overpass land-use fetch is launched in a background
thread at the very start of the request — at the same time as the elevation
fetch, not after candidate generation — since it only needs the drawn
polygon's bbox, not the terrain. This overlaps two independent network calls
that used to run strictly sequentially; a failure in the background fetch
degrades to the same "filter skipped, plus a warning" behavior as before,
never a hard failure. The contour-upload path is unaffected (it never
fetches elevation over the network, so there's nothing to overlap).

---

## External APIs

| Provider | Purpose | Status |
|---|---|---|
| Open-Meteo | Historical rainfall | **Implemented** (`app/services/rainfall_service.py`) |
| Copernicus DEM (AWS S3 Open Data) | Primary elevation source — static COG tile reads, no rate limit | **Implemented** (`app/providers/elevation/copernicus_dem.py`) |
| OpenZenith | Elevation fallback tier 1 (points Copernicus DEM couldn't return) | **Implemented** (`app/providers/elevation/open_elevation.py`) |
| Open-Elevation | Elevation fallback tier 2 | **Implemented** (same file) |
| OpenTopoData | Elevation fallback tier 3 | **Implemented** (same file) |
| Overpass (OpenStreetMap) | Buildings/roads/rivers/water bodies for the land-use constraint filter | **Implemented** (`app/providers/landuse/overpass.py`) |
| NASA POWER / IMD | Rainfall alternatives | Not yet implemented |

All five implemented providers above share a circuit breaker
(`app/utils/circuit_breaker.py`): once one is seen rate-limited or
unreachable, further requests skip it immediately for
`CIRCUIT_BREAKER_COOLDOWN_S` instead of re-discovering the same failure
from scratch on every new analysis.

Every external HTTP request also sends a descriptive `User-Agent`
(`app/utils/http_client.py`). This was found to matter, not just be
courtesy: httpx's generic default User-Agent got this project bot-filtered
(HTTP 406) by the flagship Overpass instance and rejected (HTTP 403,
"only available to white-listed usages") by a community mirror — both
resolved immediately by identifying the client properly instead of
looking like an anonymous script.

---

## Running Tests

```bash
# Ensure the sample KML is in data/ first
pytest tests/ -v
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py             # FastAPI app factory
│   ├── config.py           # All settings (Pydantic BaseSettings)
│   ├── api/                # HTTP route handlers
│   ├── services/           # Business logic orchestration
│   ├── algorithms/         # Pure computational algorithms
│   ├── providers/          # External API integrations (elevation, rainfall)
│   ├── models/             # Data classes and Pydantic schemas
│   └── utils/              # Geo helpers, GeoJSON, storage
├── tests/                  # Pytest test suite
├── data/                   # Place contours_1m.kml here
├── requirements.txt
└── .env.example
```

---

## Algorithms Used

| Algorithm | File | Reference |
|---|---|---|
| Contour → DEM | `algorithms/interpolation.py` | scipy griddata (linear + nearest) |
| Selected-area → DEM | `services/terrain_service.py` (`build_terrain_model_from_area`) | Copernicus DEM tile reads (OpenZenith → Open-Elevation → OpenTopoData fallback) + nearest-neighbour gap fill |
| Depression Filling | `algorithms/depression.py` | Barnes et al. (2014) Priority-Flood |
| Flow Direction | `algorithms/flow_direction.py` | D8 steepest-descent |
| Flow Accumulation | `algorithms/flow_accumulation.py` | Kahn's topological sort |
| Catchment Delineation | `algorithms/watershed.py` | Upstream BFS on reverse flow graph |
| Slope | `algorithms/slope.py` | NumPy finite difference gradient |
| Scoring | `algorithms/scoring.py` | Min-max normalised weighted sum |
| Runoff | `services/runoff_service.py` | Rational Method: `Q = C × P × A` |
| Pond Sizing | `services/pond_service.py` | `storage = runoff × retention factor` |
| Land-use Constraint | `services/landuse_service.py` | Buffered OSM geometries, unioned; candidate point intersection test |

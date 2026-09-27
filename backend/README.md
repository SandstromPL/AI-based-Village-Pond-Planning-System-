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
box is fetched live from Open-Elevation, then fed into the same terrain
pipeline as the contour-upload flow.

---

## Analysis Pipeline

```
KML/KMZ Upload                          Map-drawn Polygon
    ↓                                        ↓
File Validation & Parsing            Bounding box + size/grid-point caps
    ↓                                        ↓
DEM via contour interpolation        DEM via Open-Elevation grid fetch
    │                                        │ (cached, retried, nearest-
    │                                        │  neighbour fallback on gaps)
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
        Hard Filters (slope, catchment size)
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

### Terrain & candidate generation

| Variable | Default | Description |
|---|---|---|
| `DEM_RESOLUTION_M` | `30` | DEM grid cell size (metres) |
| `MAX_SLOPE_DEG` | `15` | Hard filter: reject candidates with slope > this |
| `MIN_CATCHMENT_KM2` | `0.005` | Hard filter: reject if catchment < this |
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
| `OPEN_ELEVATION_URL` | Open-Elevation public API | Elevation lookup for the drawn area |
| `ELEVATION_BATCH_SIZE` | `50` | Points per Open-Elevation request |
| `ELEVATION_MAX_RETRIES` | `1` | Retries per batch before giving up |
| `ELEVATION_MAX_CONCURRENT_REQUESTS` | `5` | Batches fetched in parallel (bounds wall-clock time) |
| `ELEVATION_FALLBACK_ENABLED` / `OPENTOPODATA_URL` | `true` / OpenTopoData public API | Fallback provider for any points Open-Elevation can't return — including its domain being unreachable from a given network while others are fine |
| `SELECTED_AREA_MAX_KM2` | `25` | Reject polygons larger than this |
| `SELECTED_AREA_MAX_GRID_POINTS` | `2500` | Auto-coarsen DEM resolution above this many cells |

---

## External APIs

| Provider | Purpose | Status |
|---|---|---|
| Open-Meteo | Historical rainfall | **Implemented** (`app/services/rainfall_service.py`) |
| Open-Elevation | Elevation for selected-area analysis | **Implemented** (`app/providers/elevation/open_elevation.py`) |
| OpenTopoData | Elevation fallback (points Open-Elevation couldn't return) | **Implemented** (same file) |
| OpenZenith | Elevation validation (contour path) | Not yet implemented |
| NASA POWER / IMD | Rainfall alternatives | Not yet implemented |

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
| Selected-area → DEM | `services/terrain_service.py` (`build_terrain_model_from_area`) | Open-Elevation grid fetch + nearest-neighbour gap fill |
| Depression Filling | `algorithms/depression.py` | Barnes et al. (2014) Priority-Flood |
| Flow Direction | `algorithms/flow_direction.py` | D8 steepest-descent |
| Flow Accumulation | `algorithms/flow_accumulation.py` | Kahn's topological sort |
| Catchment Delineation | `algorithms/watershed.py` | Upstream BFS on reverse flow graph |
| Slope | `algorithms/slope.py` | NumPy finite difference gradient |
| Scoring | `algorithms/scoring.py` | Min-max normalised weighted sum |
| Runoff | `services/runoff_service.py` | Rational Method: `Q = C × P × A` |
| Pond Sizing | `services/pond_service.py` | `storage = runoff × retention factor` |

# Village Pond Planning API — Phase 2

> **AI-based Village Pond Planning System** | CSD Assignment 1 | Phase 2 Backend

A FastAPI backend that accepts a contour map (KML/KMZ), analyzes terrain and hydrology, and recommends suitable pond locations with catchment information.

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
# Edit .env if you want to change DEM resolution or thresholds

# 5. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/docs** for the interactive API docs (Swagger UI).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/analyzeContour` | Upload KML/KMZ → full analysis |
| `GET`  | `/api/v1/analysis/{id}` | Retrieve a previous analysis |
| `GET`  | `/api/v1/health` | Service health check |

### Example: Analyze a contour map

```bash
curl -X POST http://localhost:8000/api/v1/analyzeContour \
  -F "file=@data/contours_1m.kml" | python3 -m json.tool | head -80
```

---

## Analysis Pipeline

```
KML/KMZ Upload
    ↓
File Validation & Parsing
    ↓
Terrain Model (DEM via contour interpolation)
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
[PLACEHOLDER] Rainfall / Runoff / Pond Sizing
    ↓
Structured JSON + GeoJSON layers
```

---

## Configuration

All parameters are in `.env` (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DEM_RESOLUTION_M` | `30` | DEM grid cell size (metres) |
| `MAX_SLOPE_DEG` | `15` | Hard filter: reject candidates with slope > this |
| `MIN_CATCHMENT_KM2` | `0.05` | Hard filter: reject if catchment < this |
| `MAX_CANDIDATES` | `5` | Maximum candidates to return |
| `FLOW_ACC_PERCENTILE` | `99` | Top percentile for flow-convergence seeds |
| `MIN_CANDIDATE_DISTANCE_M` | `200` | Minimum separation between candidates |

---

## External API Placeholders

The following APIs are marked `# [EXTERNAL_API_PLACEHOLDER]` and return stub data in Phase 2:

| Provider | Purpose | Phase 3 action |
|---|---|---|
| OpenZenith | Elevation validation | Add key to `OPENZENITH_API_KEY` |
| Open-Meteo | Historical rainfall | No key needed — implement provider |
| NASA POWER | Rainfall alternative | Implement provider |
| IMD | Indian rainfall data | Add key to `IMD_API_KEY` |

Implement the provider in `app/providers/rainfall/` following the base class in `app/providers/rainfall/base.py`.

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
│   ├── providers/          # External API integrations (placeholders)
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
| Depression Filling | `algorithms/depression.py` | Barnes et al. (2014) Priority-Flood |
| Flow Direction | `algorithms/flow_direction.py` | D8 steepest-descent |
| Flow Accumulation | `algorithms/flow_accumulation.py` | Kahn's topological sort |
| Catchment Delineation | `algorithms/watershed.py` | Upstream BFS on reverse flow graph |
| Slope | `algorithms/slope.py` | NumPy finite difference gradient |
| Scoring | `algorithms/scoring.py` | Min-max normalised weighted sum |

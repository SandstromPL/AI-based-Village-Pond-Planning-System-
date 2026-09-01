# Village Pond Planning System — Architecture & Usage Guide (`working.md`)

This document provides a comprehensive technical overview of the backend codebase flow, API testing guide (curl & Postman), evaluation metrics for site selection, and architectural design for constraint filtering (e.g., avoiding buildings, roads, villages, and rivers).

---

## 1. Codebase Architecture & Execution Flow

The system is structured as a 7-stage layered pipeline. The API layer acts as an orchestrator, delegating heavy geospatial and numerical computations to dedicated service and algorithm modules.

```
                    ┌────────────────────────────────────────┐
                    │      Client / API Consumer             │
                    └───────────────────┬────────────────────┘
                                        │ POST /analyzeContour (KML/KMZ File)
                                        ▼
                    ┌────────────────────────────────────────┐
                    │ FastAPI Route (app/api/analysis.py)    │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │ Orchestrator (services/analysis_service)│
                    └───┬──────┬──────┬──────┬──────┬──────┬─┘
                        │      │      │      │      │      │
     ┌──────────────────┘      │      │      │      │      └──────────────────┐
     ▼                         ▼      │      │      ▼                         ▼
┌──────────────┐      ┌─────────────┐ │      │ ┌──────────────┐     ┌───────────────────┐
│ KML Service  │      │Terrain Svc  │ │      │ │Candidate Svc │     │ Placeholder Svcs  │
│ (kml_service)│      │(terrain_svc)│ │      │ │(candidate_svc│     │(rainfall/runoff/  │
└──────┬───────┘      └──────┬──────┘ │      │ └──────┬───────┘     │ pond_service)     │
       │                     │        │      │        │             └───────────────────┘
       ▼                     ▼        │      │        ▼
┌──────────────┐      ┌─────────────┐ │      │ ┌──────────────┐
│Normalized    │      │Interpolation│ │      │ │  Catchment   │
│Contour Data  │      │   & Slope   │ │      │ │ Delineation  │
└──────────────┘      └──────┬──────┘ │      │ └──────┬───────┘
                             │        │      │        │
                             ▼        ▼      ▼        ▼
                      ┌─────────────────────────────────┐
                      │  Priority-Flood Depression Fill │
                      │  D8 Flow Dir & Accumulation     │
                      │  Multi-Factor Scoring & Ranking │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │  GeoJSON Layers & JSON Output   │
                      └─────────────────────────────────┘
```

### Detailed Pipeline Flow Step-by-Step

1. **File Ingestion & Parsing (`app/services/kml_service.py`)**:
   - Accepts `.kml` (raw XML) or `.kmz` (ZIP compressed archive containing KML).
   - Detects XML namespaces (`http://www.opengis.net/kml/2.2`).
   - Extracts contour elevations from `<name>` tags and 3D line coordinates from `<LineString><coordinates>`.
   - Filters out non-line placemarks (e.g., label markers) and calculates the geographic bounding box ($WGS84$).
   - Returns a format-agnostic `NormalizedContourData` dataclass.

2. **Terrain Surface & DEM Reconstruction (`app/services/terrain_service.py` & `app/algorithms/`)**:
   - **CRS Projection (`app/utils/geo.py`)**: Auto-detects UTM EPSG code from longitude centroid (e.g., `EPSG:32644` for Zone 44N in India) to execute all spatial calculations in metric units (metres).
   - **Contour Sampling & Interpolation (`app/algorithms/interpolation.py`)**: Point cloud sampled at 10m intervals along contour vectors; interpolates regular 2D elevation grid (DEM) using `scipy.interpolate.griddata` (linear barycentric interpolation with nearest-neighbour edge fill).
   - **Slope Calculation (`app/algorithms/slope.py`)**: Computes finite-difference directional elevation gradients ($\frac{\partial Z}{\partial x}, \frac{\partial Z}{\partial y}$) using NumPy to calculate per-cell slope in degrees ($\theta = \arctan \sqrt{(\frac{\partial Z}{\partial x})^2 + (\frac{\partial Z}{\partial y})^2}$).
   - **Hydrological Conditioning (`app/algorithms/depression.py`)**: Applies Priority-Flood algorithm (Barnes et al., 2014) using a min-heap to raise artificial sinks/pits in the DEM to their spill elevation, ensuring continuous downhill drainage.

3. **Hydrological Flow Network (`app/services/catchment_service.py` & `app/algorithms/`)**:
   - **D8 Flow Direction (`app/algorithms/flow_direction.py`)**: For each cell, evaluates 8 adjacent cells and calculates distance-weighted elevation drop ($\Delta Z / d$, where diagonal distance $d = \text{resolution} \times \sqrt{2}$). Assigns flow direction code (0 to 7) along steepest descent.
   - **Flow Accumulation (`app/algorithms/flow_accumulation.py`)**: Constructs a Directed Acyclic Graph (DAG) of flow paths; processes cells in topological order (Kahn’s algorithm) to count total upstream contributing cells for every grid cell.
   - **Catchment Delineation (`app/algorithms/watershed.py`)**: Performs upstream Breadth-First Search (BFS) on the inverted D8 flow graph starting from pour points; vectorizes boolean cell masks into GeoJSON WGS84 Polygons and calculates area in $\text{km}^2$.

4. **Candidate Generation & Spatial NMS (`app/services/candidate_service.py`)**:
   - Generates candidate seeds from two independent hydrological signals:
     1. **Depression Seeds**: Local minima in filled DEM where pre-fill elevation differs from post-fill elevation ($\Delta Z > 0.1\text{m}$).
     2. **Flow Convergence Seeds**: Cells with high flow accumulation (top 99th percentile).
   - Merges seeds and applies **Spatial Non-Maximum Suppression (NMS)** using Haversine distance to eliminate spatial clustering (ensuring candidates are separated by at least `MIN_CANDIDATE_DISTANCE_M`).
   - Applies hard constraint filters (slope $> 15^\circ$ or catchment area $< 0.005\text{ km}^2$).

5. **Multi-Factor Scoring & Recommendation (`app/algorithms/scoring.py`)**:
   - Evaluates surviving candidates across 5 terrain and hydrological metrics.
   - Normalizes factors to a 0–100 scale across candidate pools.
   - Assigns a final weighted score, ranks candidates, generates structured reasoning strings, and identifies the Rank-1 recommendation.

6. **GeoJSON Layer Assembly & Response Delivery (`app/api/analysis.py`)**:
   - Formats vector contours, candidate point features, catchment polygons, and recommended locations into standard GeoJSON FeatureCollections.
   - Caches output in-memory by `analysis_id` (`app/utils/storage.py`) and returns complete JSON response.

---

## 2. Running the API: Step-by-Step Guide

### 2.1 Starting the Local Server

Open a terminal in the project directory:

```bash
cd /home/paritosh/Desktop/Projects/CSD/ASSIGNMENT_01/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify server status:
- Interactive Swagger UI: `http://localhost:8000/docs`
- Interactive ReDoc: `http://localhost:8000/redoc`
- Health Endpoint: `http://localhost:8000/api/v1/health`

---

### 2.2 Using `curl`

#### Endpoint 1: Health Check (`GET`)
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

**Expected Response**:
```json
{
  "status": "ok",
  "version": "0.2.0",
  "phase": "Phase 2 — Terrain & Catchment Analysis"
}
```

#### Endpoint 2: Analyze Contour Map (`POST`)
Upload a KML or KMZ file as `multipart/form-data`:

```bash
curl -X POST "http://localhost:8000/api/v1/analyzeContour" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@data/contours_1m.kml"
```

*Tip: Pretty-print response using python or `jq`*:
```bash
curl -s -X POST "http://localhost:8000/api/v1/analyzeContour" \
  -F "file=@data/contours_1m.kml" | python3 -m json.tool
```

#### Endpoint 3: Fetch Previous Analysis (`GET`)
Using the `analysis_id` returned from the POST response:

```bash
curl -X GET "http://localhost:8000/api/v1/analysis/YOUR_ANALYSIS_ID_HERE"
```

---

### 2.3 Using Postman

#### Method 1: `POST /api/v1/analyzeContour` (Contour Upload)
1. Launch Postman and create a **New Request**.
2. Set HTTP Method to **`POST`**.
3. Enter Request URL: `http://localhost:8000/api/v1/analyzeContour`.
4. Click on the **`Body`** tab below the URL bar.
5. Select **`form-data`**.
6. In the key column, type **`file`**. Change the key type dropdown from **Text** to **File**.
7. In the value column, click **Select Files** and choose `contours_1m.kml` (or your KMZ file).
8. Click **Send**.

#### Method 2: `GET /api/v1/analysis/:analysis_id` (Fetch Cached Result)
1. Create a **New Request**.
2. Set HTTP Method to **`GET`**.
3. Enter Request URL: `http://localhost:8000/api/v1/analysis/<analysis_id_from_post_response>`.
4. Click **Send**.

---

## 3. Site Selection Evaluation Metrics

The final decision algorithm evaluates each potential candidate site using a multi-criteria decision matrix (MCDM). In Phase 2, five primary terrain and hydrological factors are computed and normalized:

| Metric | Weight | Rationale & Mathematical Formula |
|---|---|---|
| **1. Catchment Area ($A_{catch}$)** | **35%** | **Water Inflow Capacity**: Measures total upstream area ($\text{km}^2$) contributing runoff to the pour point via BFS graph traversal. Larger catchments collect significantly more rainwater volume. |
| **2. Flow Accumulation ($N_{acc}$)** | **25%** | **Stream Convergence Strength**: Measures number of upstream grid cells draining into the location. High values identify natural surface water convergence channels and natural drainage axes. |
| **3. Terrain Slope ($\theta$)** | **20%** | **Construction Suitability**: Inverted normalization (gentler slopes score higher). Slopes $< 5^\circ$ minimize earth excavation costs, reduce bund construction effort, and prevent severe embankment erosion. |
| **4. Relative Relief / Elevation ($Z_{rel}$)** | **10%** | **Gravity Drainage Feasibility**: Inverted normalization (lower elevation relative to local terrain scores higher). Ensures natural gravity-fed water inflow from higher surrounding topography. |
| **5. Natural Depression Depth ($\Delta Z_{fill}$)** | **10%** | **Excavation Efficiency**: Measures depth ($\text{meters}$) of natural terrain bowl ($\text{filled\_dem} - \text{raw\_dem}$). Sites with natural land depressions require substantially less earthwork volume to impound target water storage. |

### Scoring Formula

For candidate $i$ among accepted candidates:

$$S_i = w_{cat} \cdot \widehat{A}_i + w_{flow} \cdot \widehat{N}_i + w_{slope} \cdot (100 - \widehat{\theta}_i) + w_{rel} \cdot (100 - \widehat{Z}_i) + w_{dep} \cdot \widehat{\Delta Z}_i$$

Where $\widehat{X}_i$ represents min-max feature normalization to the range $[0, 100]$.

---

## 4. Query Handling: Excluding Unsuitable Areas (Buildings, Roads, Rivers, Villages)

### Current Behavior (Phase 2)
In Phase 2, contour maps (KML/KMZ) provide elevation contours. The algorithm automatically avoids high-risk areas using two indirect terrain rules:
1. **Steep Slope Rejection (`REJECTED_SLOPE`)**: Excludes steep embankments and built structure slopes (slope $> 15^\circ$).
2. **Micro-catchment Rejection (`REJECTED_CATCHMENT`)**: Rejects locations with small catchment area ($< 0.005\text{ km}^2$), which filters out minor roof runoff or artificial ditches.

---

### Production Design (Phase 3 Spatial Constraint Layer Architecture)

To explicitly prevent placing ponds on top of buildings, roads, existing rivers, or village settlements, a **Modular Constraint Overlay Service** is integrated into the candidate pipeline.

```
                       ┌───────────────────────────────┐
                       │  Candidate Generation Engine  │
                       └───────────────┬───────────────┘
                                       │ Raw Candidates
                                       ▼
                       ┌───────────────────────────────┐
                       │   External Spatial Data       │
                       │   (OSM / Bhuvan / LULC Mask)   │
                       └───────────────┬───────────────┘
                                       │ Vector Polygons & Buffers
                                       ▼
                       ┌───────────────────────────────┐
                       │  Spatial Intersection Filter  │
                       │  (Shapely / GeoPandas R-Tree) │
                       └───────────────┬───────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │
                ▼                                             ▼
     [Candidate Intersects Exclusion Zone]      [Candidate in Valid Zone]
                │                                             │
                ▼                                             ▼
     Candidate Status = REJECTED                   Candidate Status = ACCEPTED
     Reason: "Within 50m road buffer"               Proceed to Scoring
```

#### Step-by-Step Constraint Mechanism:

1. **Exclusion Layer Ingestion**:
   Vector datasets (from OpenStreetMap, Land Use/Land Cover (LULC) maps, or government GIS portals) are loaded into spatial R-Trees (`geopandas.sjoin`):
   - **Settlement Layer** (Villages, Residential Structures, Homesteads)
   - **Infrastructure Layer** (Roads, Highways, Railways, Power lines)
   - **Hydrological Layer** (Active perennial rivers, major canals, existing lakes/reservoirs)

2. **Buffer Zone Definition**:
   Set mandatory safety buffer distances around features:
   - Roads / Highways: **50m buffer**
   - Buildings / Homesteads: **100m buffer**
   - Existing River Channels: **30m buffer** (to prevent stream bed alteration)
   - High-voltage power lines: **75m buffer**

3. **Spatial Exclusion Masking (`candidate_service.py`)**:
   Before a candidate is accepted, its spatial geometry (point location $(x, y)$ and calculated catchment polygon $P_{catch}$) is checked against the exclusion mask:
   ```python
   # Conceptual constraint checking flow (Phase 3)
   for candidate in candidates:
       # Check spatial intersection with exclusion layers
       if settlement_mask.intersects(candidate.geometry.buffer(100)):
           candidate.status = CandidateStatus.REJECTED_CONSTRAINT
           candidate.rejection_reason = "Location within 100m village settlement buffer"
       elif road_mask.intersects(candidate.geometry.buffer(50)):
           candidate.status = CandidateStatus.REJECTED_CONSTRAINT
           candidate.rejection_reason = "Location within 50m road infrastructure buffer"
       elif river_mask.intersects(candidate.geometry.buffer(30)):
           candidate.status = CandidateStatus.REJECTED_CONSTRAINT
           candidate.rejection_reason = "Location inside active river bed buffer"
   ```

4. **Land Suitability Penalty (Soft Constraint)**:
   For candidates passing hard spatial buffers, land cover type (agricultural vs. barren vs. forest) is factored into the scoring matrix as a suitability weight multiplier.

---

## 5. Internal & External APIs Usage Guide

### 5.1 Internal APIs (Current Backend)

The backend currently exposes three internal REST endpoints.

#### 1. Analyze Contour (`POST /api/v1/analyzeContour`)
Analyzes a KML/KMZ file and returns pond candidates.
*   **cURL:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/analyzeContour" \
      -H "accept: application/json" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@data/contours_1m.kml"
    ```
*   **Postman:**
    1. Method: **POST**
    2. URL: `http://localhost:8000/api/v1/analyzeContour`
    3. Body Tab -> Select **form-data**
    4. Key: `file` (Change type from Text to File) -> Value: Select `contours_1m.kml`
    5. Click **Send**

#### 2. Get Analysis Result (`GET /api/v1/analysis/{analysis_id}`)
Retrieves a previously computed analysis from memory.
*   **cURL:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/analysis/<ANALYSIS_ID>" \
      -H "accept: application/json"
    ```
*   **Postman:**
    1. Method: **GET**
    2. URL: `http://localhost:8000/api/v1/analysis/<ANALYSIS_ID>`
    3. Click **Send**

#### 3. Health Check (`GET /api/v1/health`)
Verifies if the backend service is running.
*   **cURL:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/health" \
      -H "accept: application/json"
    ```
*   **Postman:**
    1. Method: **GET**
    2. URL: `http://localhost:8000/api/v1/health`
    3. Click **Send**

### 5.2 External APIs (Phase 3 Integrations)

The architecture is prepared to consume external APIs for rainfall, runoff estimation, and elevation validation. These are currently implemented as placeholder services (`app/services/rainfall_service.py`, etc.).

#### 1. Open-Meteo Historical Weather API (Rainfall)
Used to fetch historical daily precipitation data for runoff calculation.
*   **Endpoint:** `GET https://archive-api.open-meteo.com/v1/archive`
*   **cURL:**
    ```bash
    curl -X GET "https://archive-api.open-meteo.com/v1/archive?latitude=21.2632&longitude=81.2828&start_date=2015-01-01&end_date=2024-12-31&daily=precipitation_sum&timezone=auto"
    ```
*   **Postman:**
    1. Method: **GET**
    2. URL: `https://archive-api.open-meteo.com/v1/archive`
    3. Params Tab:
        *   `latitude`: `21.2632`
        *   `longitude`: `81.2828`
        *   `start_date`: `2015-01-01`
        *   `end_date`: `2024-12-31`
        *   `daily`: `precipitation_sum`
        *   `timezone`: `auto`
    4. Click **Send**

#### 2. Open-Elevation / OpenZenith API (Elevation Validation)
Used to cross-validate KML contour elevations against global DEM datasets (e.g., SRTM).
*   **Endpoint:** `POST https://api.open-elevation.com/api/v1/lookup`
*   **cURL:**
    ```bash
    curl -X POST "https://api.open-elevation.com/api/v1/lookup" \
      -H "Accept: application/json" \
      -H "Content-Type: application/json" \
      -d '{"locations":[{"latitude":21.2632,"longitude":81.2828}]}'
    ```
*   **Postman:**
    1. Method: **POST**
    2. URL: `https://api.open-elevation.com/api/v1/lookup`
    3. Body Tab -> Select **raw** -> Set format to **JSON**
    4. Content: `{"locations":[{"latitude":21.2632,"longitude":81.2828}]}`
    5. Click **Send**

#### 3. Bhuvan / ISRO / ESRI Land Cover API (Runoff Coefficient)
Used to determine soil permeability and land use (LULC) to calculate the Rational Method Runoff Coefficient.
*   *(Example using ESRI Land Cover Image Service)*
*   **Endpoint:** `GET https://landcover.esri.com/arcgis/rest/services/LandCover/MapServer/identify`
*   **cURL:**
    ```bash
    curl -X GET "https://landcover.esri.com/arcgis/rest/services/LandCover/MapServer/identify?geometry=81.2828,21.2632&geometryType=esriGeometryPoint&returnGeometry=false&f=json"
    ```
*   **Postman:**
    1. Method: **GET**
    2. URL: `https://landcover.esri.com/arcgis/rest/services/LandCover/MapServer/identify`
    3. Params Tab:
        *   `geometry`: `81.2828,21.2632`
        *   `geometryType`: `esriGeometryPoint`
        *   `returnGeometry`: `false`
        *   `f`: `json`
    4. Click **Send**

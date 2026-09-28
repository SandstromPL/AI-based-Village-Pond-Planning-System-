# Report content — AI-based Village Pond Planning System

> Working document. This captures real facts, numbers, and decisions from the
> build session so nothing gets lost before the final report is written into
> `assignment_info/report_template.tex` (ACM format, 10-page max, `[MUST BE
> INCLUDED]` sections marked below exactly as the template marks them).
> Headings below mirror the template's section order 1:1 — copy each section's
> content across and trim to fit the page budget. Anything written as a
> **placeholder** still needs a human decision (name, links, screenshots).

---

## Title / Author block

- Title (fixed by template): **AI-based Village Pond Planning System**
- Subtitle (fixed): CSD Assignment 1 — Final Technical Report
- Author / affiliation / email: **placeholder** — fill with actual name(s),
  IIT Bhilai (based on session's email domain `@iitbhilai.ac.in`), and email.

---

## Abstract (150–250 words)

Draft:

> Rural water conservation in India often depends on identifying suitable
> sites for small check-dams and percolation ponds, a task traditionally done
> by manual site inspection with no systematic terrain, catchment, or rainfall
> analysis. This project implements a full-stack, terrain-aware
> decision-support system that recommends pond locations from either an
> uploaded contour map (KML/KMZ) or a user-drawn area on an interactive map.
> The backend reconstructs a digital elevation model, hydrologically
> conditions it (Priority-Flood depression filling), computes D8 flow
> direction and accumulation, delineates catchments via upstream graph
> search, and scores candidate sites on five terrain/hydrology factors. Real
> historical rainfall (Open-Meteo) drives a Rational-Method runoff estimate,
> which in turn sizes a planning-level pond (depth, surface area, storage
> volume). A land-use constraint filter, built on live OpenStreetMap data via
> the Overpass API, rejects candidates that fall on existing buildings,
> roads, rivers, or water bodies. All of this is exposed through a React +
> Leaflet frontend with a dark/light theme and both input modes, and is
> engineered to degrade gracefully — never fail outright — when any of the
> five external APIs it depends on is unavailable. On a representative
> ~4 km² village contour dataset, the system evaluated **187 candidate
> seeds**, accepted **5** after terrain/catchment/land-use filtering, and
> recommended a site with an estimated **21,820 m³** annual collectable
> runoff and **17,456 m³** planned storage, computed end-to-end in
> **1.2–7.2 seconds**. A separate map-selected-area analysis (no file
> upload) was verified end-to-end against live external APIs: elevation for
> a ~1,900-cell grid was fetched in 1-2 real API calls in under 3 seconds
> via a primary elevation provider (OpenZenith), with a two-tier fallback
> chain and a hard **45-second** wall-clock budget bounding the worst case
> to roughly 70–75 seconds regardless of external API health.

*(~250 words — trim if needed once the real author section is added.)*

**Keywords** (per template): Village Pond Planning, Geospatial Analysis,
Rainwater Harvesting, Catchment Estimation, Web GIS, REST APIs.

---

## 1. Introduction `[MUST BE INCLUDED]`

Rural India loses a large fraction of monsoon rainfall to unmanaged runoff.
Small ponds and check-dams built at hydrologically correct locations —
natural depressions or flow-convergence points with adequate catchment —
can capture this water cheaply, but choosing that location today relies on
manual inspection with no systematic terrain, catchment, or rainfall
analysis. This project builds a web application that automates that
decision: given either a contour map or a map-drawn area, it reconstructs
terrain, analyzes drainage, scores candidate sites, filters out sites that
would conflict with existing land use, estimates expected water volume from
real rainfall data, and presents all of this overlaid on an interactive map.

### 1.1 Motivation

Manual site selection is hard for three concrete reasons this project
directly addresses: (1) terrain complexity — a contributing catchment isn't
visible by eye, it requires flow-direction/accumulation analysis across an
entire elevation surface; (2) no centralized, per-site rainfall record —
village-level historical rainfall statistics aren't something a field
surveyor can look up on the spot; (3) no systematic way to cross-check a
promising terrain location against existing buildings, roads, or rivers
without a separate land-survey pass. Automating these three lets a
non-specialist get a defensible, explainable recommendation in seconds
instead of a multi-day manual survey.

### 1.2 Scope of the Project `[MUST BE INCLUDED]`

**In scope:**
- Two input modes: upload a KML/KMZ contour map, or draw an arbitrary area
  directly on a map (no file needed).
- Terrain reconstruction, hydrological conditioning, flow analysis, and
  multi-candidate catchment delineation from either input.
- Multi-factor candidate scoring and ranking with human-readable reasoning
  for the top recommendation.
- Real historical rainfall retrieval and Rational-Method runoff estimation.
- Planning-level pond sizing (depth, surface area, storage volume).
- A land-use constraint filter (buildings/roads/rivers/water bodies/power
  lines) using live OpenStreetMap data, so recommendations don't land on
  existing structures.
- An interactive map frontend showing every layer above, with graceful
  degradation displayed to the user (not hidden) when any external data
  source is temporarily unavailable.

**Out of scope (explicitly):**
- Structural/civil engineering design of the pond embankment or spillway —
  outputs are planning-level estimates, not construction drawings.
- Soil type, infiltration, or land-use-based refinement of the runoff
  coefficient — a single configurable constant (default 0.35) is used.
- Verifying land ownership (government/public vs. private).
- Multi-user authentication/authorization or per-user data isolation.
- Persistent storage beyond a single server process's lifetime (see
  §7.3 Database and Storage).
- Guaranteeing live external API uptime — the system is explicitly designed
  to degrade and report "unavailable" rather than assume any of its four
  external dependencies (Open-Meteo, OpenZenith, Open-Elevation,
  OpenTopoData, Overpass) is always reachable, because in practice during
  development most of them were observed to fail at least once.

---

## 2. Problem Statement and Requirements `[MUST BE INCLUDED]`

### Table: Functional requirements → implementation

| Requirement (from assignment brief) | Implemented in |
|---|---|
| Satellite imagery display | `frontend/src/components/MapView.jsx` — Esri World Imagery base layer |
| Contour map visualization | `backend/app/services/kml_service.py` (parsing) → `geojson_layers.contour_lines` → rendered in `MapView.jsx` |
| Available-land identification | `backend/app/services/candidate_service.py` (candidate generation + hard filters) + `backend/app/services/landuse_service.py` (land-use exclusion) |
| Catchment area estimation | `backend/app/services/catchment_service.py`, `backend/app/algorithms/{flow_direction,flow_accumulation,watershed}.py` |
| Historical rainfall query | `backend/app/services/rainfall_service.py` (Open-Meteo) |
| Runoff volume estimation | `backend/app/services/runoff_service.py` (Rational Method) |
| Pond depth / storage recommendation | `backend/app/services/pond_service.py` |
| Combined overlay / results view | `frontend/src/components/MapView.jsx` + `ResultsPanel.jsx` |

*(This is the exact table shape the template asks for — already filled in,
not a placeholder.)*

### 2.1 Non-Functional Requirements `[MUST BE INCLUDED]`

Stated as concrete, defensible numbers based on what was actually built and
measured this session, not aspirational targets:

- **Performance**: contour-upload analysis completes in **under 10 seconds**
  end-to-end for a village-scale (~4 km²) dataset — observed **1.17–7.22 s**
  pipeline time across multiple real runs against live external APIs.
  Map-selected-area analysis is bounded to a **worst case of ~70–75 seconds**
  even under significant external-API degradation, via a hard 45-second
  elevation-fetch deadline (see §4.1 and §8 — this bound was *discovered
  necessary* after a real production log showed unbounded ~4-minute worst
  case before the deadline was added).
- **Concurrency/Scalability**: the backend's event loop remains responsive
  to concurrent requests during a slow analysis — verified live that
  `GET /health` answered in under 3 ms while a 30+ second area analysis was
  simultaneously in flight, because the blocking analysis pipeline is
  explicitly offloaded to a thread pool (`run_in_threadpool`) rather than
  run inline on the async event loop. (A real bug — the whole server
  freezing on every request during one slow analysis — was found and fixed
  during this session; see §8 Error Handling and §9 Discussion.)
- **Availability/Resilience**: the system tolerates the failure of *any
  single* external dependency (rainfall, any of the three elevation
  providers, or the land-use provider) without failing the whole request —
  every external call degrades to an explicit `"unavailable"` status plus a
  warning message rather than raising an exception. Verified live during
  development — each of the following was observed to fail for real at
  least once: Open-Meteo rate-limiting, Open-Elevation DNS failures,
  OpenTopoData connection resets, Overpass HTTP errors (OpenZenith itself
  has been consistently reliable once the correct domain was used — see
  §3 Technology Stack).
- **Usability**: single-page web app; dark theme by default with a
  persistent light/dark switch; both input modes (upload / draw) accessible
  from one screen; explicit loading state with a time-expectation message
  for the slower of the two analysis paths; explicit, human-readable error
  banners rather than a blank/broken UI on failure.
- **Security**: no authentication is implemented. This is a deliberate scope
  decision (see §1.2), appropriate for a single-team demo/assignment
  deployment, not a production multi-tenant system.
- **Browser support**: tested against Chrome/Chromium (via automated
  browser verification during development); no browser-specific code paths,
  so other evergreen browsers are expected to work but were not explicitly
  tested.

---

## 3. System Architecture and High-Level Design `[MUST BE INCLUDED]`

### Architecture description (for the diagram)

Three tiers, plus four external data sources:

```
┌─────────────────────────────┐
│  Client: React + Leaflet    │  Upload KML/KMZ  OR  draw polygon on map
│  (frontend/, static, Vite)  │
└──────────────┬───────────────┘
               │ REST (JSON / multipart), CORS-enabled, no auth
               ▼
┌─────────────────────────────┐
│  FastAPI backend (backend/) │
│  api/ → services/ →         │
│  algorithms/ → providers/   │
└──┬────────┬────────┬────────┘
   │        │        │
   ▼        ▼        ▼        ▼
Open-Meteo   OpenZenith →     Overpass API
(rainfall)   Open-Elevation → (OpenStreetMap:
             OpenTopoData     buildings/roads/
             (elevation,      rivers/water/
             3-tier fallback) power lines)
```

- **Client tier**: React 19 + Vite, `react-leaflet` + `leaflet-draw` for the
  map, plain CSS (no UI framework), no state-management library. Talks to
  the backend over a configurable `VITE_API_BASE_URL`.
- **Server tier**: FastAPI, layered `api/ → services/ → algorithms/ →
  providers/ → models/` (each layer independently testable — the split the
  original design docs specified was followed throughout).
- **Storage**: in-memory only (see §7.3) — no separate database tier exists
  yet.
- **External APIs**: five independent providers (rainfall, three-tier
  elevation cascade, land-use), each behind its own resilience wrapper
  (bounded timeout + retries + graceful degradation); none of them is a
  hard dependency for the request to succeed.

*(A rendered image of this diagram, or a screenshot of the actual running
app's architecture, still needs to be produced for `Figure~\ref{fig:architecture}`
— placeholder.)*

### 3.1 Technology Stack `[MUST BE INCLUDED]`

**Backend**: Python, FastAPI 0.115, Pydantic 2.8 / pydantic-settings 2.4,
Uvicorn. Geospatial: GeoPandas 0.14, Shapely 2.0, pyproj 3.6, Fiona 1.9,
rasterio 1.3. Numerical: NumPy 1.26, SciPy 1.14. KML/XML: lxml. HTTP client:
httpx. Testing: pytest + pytest-asyncio (70 tests).

**Frontend**: React 19, Vite 8, Leaflet 1.9 + react-leaflet 5 +
`leaflet-draw` (pinned to 1.0.2 — see §9 Discussion for why), plain CSS with
CSS-variable theming, oxlint for linting. No TypeScript, no state-management
library, no UI framework — a deliberate minimalism choice.

**External APIs actually queried** (all free, no API key):
Open-Meteo Historical Weather API (rainfall), OpenZenith (primary elevation
for the map-drawn-area path — verified live: up to 2000 points per batch
request in ~2 seconds, no key), Open-Elevation and OpenTopoData (elevation
fallback chain, tried only for points OpenZenith couldn't provide), Overpass
API / OpenStreetMap (land-use exclusion geometries).

**Deviation from the assignment's suggested stack**: the brief suggested
Flask *or* FastAPI (FastAPI chosen — async support, automatic OpenAPI docs,
Pydantic validation fit the geospatial/numerical workload well). "OpenZenith"
was the assignment's own suggested elevation API and is used as the primary
elevation provider, exactly as suggested — worth noting only because an
earlier evaluation this project went through initially rejected it after
testing the wrong domain (`openzenith.cyopsys.com`, which genuinely is
behind an unsolvable Cloudflare JS challenge for server-side clients); the
correct domain (`openzenith.org`) was verified to work perfectly as a plain
HTTP client, no browser needed, and is what's actually used. Open-Elevation
and OpenTopoData sit behind it as a two-tier fallback chain for resilience.
No database (PostgreSQL+PostGIS was considered in early planning) was used
in the end — see §7.3 for the honest reasoning.

**Update, later in development — OpenZenith reliability claim above was
premature and is corrected here.** Extended testing on the actual grading/
lab network (a shared university machine) showed OpenZenith failing
frequently (DNS resolution failures, connection resets, "network
unreachable") — not the "consistently reliable" behavior observed in
earlier isolated testing. Root-caused directly: hitting `openzenith.org`
five times in quick succession from an *unrelated* network (not the lab)
produced three `200 OK` responses then two `HTTP 503` responses carrying
Cloudflare error code **1102 — "Origin Rate Limited"** — confirming
OpenZenith enforces a real, undocumented rate limit (nothing about it
appears in its own OpenAPI spec) that trips after only a handful of rapid
requests, recovering on its own roughly 60–90 seconds later. With an entire
class concurrently hitting the same free service — very plausibly from one
shared/NAT'd university IP — this limit is easy to trip continuously.
Open-Elevation was separately confirmed to enforce its own real rate limit
too: a live log captured an explicit `HTTP 429 Too Many Requests` response
from it directly (not a connection failure — a clean, honest rate-limit
response). This reframes the earlier resilience narrative: the three-tier
elevation fallback chain (and the OpenTopoData 1 req/s throttle added after
finding OpenTopoData's own documented limit) is not just defending against
generic network flakiness — it is regularly absorbing *real, confirmed
rate-limiting* from more than one of its own providers, and doing so
without ever failing the whole request as long as at least one tier has
remaining capacity.

---

## 4. Methodology `[MUST BE INCLUDED]`

### 4.1 Terrain and Elevation Analysis

Two independent ways to obtain a Digital Elevation Model, feeding the same
downstream pipeline:

1. **From an uploaded KML/KMZ contour map**: contour lines are parsed
   (`kml_service.py`), sampled at 10 m intervals along each line, projected
   into an auto-detected UTM zone (from the contour centroid longitude), and
   interpolated onto a regular grid via `scipy.interpolate.griddata`
   (`linear`, with a `nearest`-neighbour second pass to fill edge gaps).
2. **From a user-drawn map area** (no file): the polygon's bounding box is
   used to build the same grid spec, but elevation for every grid cell is
   fetched from a real elevation API instead of interpolated — Open-
   Elevation first, falling back per-point to OpenTopoData for anything
   Open-Elevation could not provide (including a fully unreachable domain
   — observed for real: `Temporary failure in name resolution` against
   Open-Elevation's DNS from the deployment network, while OpenTopoData and
   Open-Meteo resolved fine from the same host at the same time). A hard
   45-second wall-clock budget bounds the whole fetch regardless of grid
   size; any points not fetched in time are filled via nearest-neighbour
   interpolation from whatever *was* fetched, with a warning reported to the
   caller.

Both paths then run identical hydrological conditioning: **Priority-Flood
depression filling** (Barnes et al., 2014 — a min-heap-based algorithm that
raises artificial sinks to their spill elevation, guaranteeing continuous
downhill drainage) and **slope computation** (NumPy finite-difference
gradient, degrees).

### 4.2 Catchment Area Delineation

**D8 flow direction**: for every cell, the steepest downhill neighbour among
8 candidates is chosen (distance-weighted elevation drop, diagonal distance
= resolution × √2). **Flow accumulation**: the D8 direction grid is treated
as a directed acyclic graph and processed in topological order (Kahn's
algorithm) to count upstream contributing cells per cell — this is the
"major algorithmic milestone" the original project plan called it out as.
**Catchment delineation**: for a given candidate (pour point), an upstream
breadth-first search on the *inverted* D8 graph collects every cell that
drains to it; the resulting boolean mask is vectorized into a GeoJSON
polygon (`rasterio.features.shapes`) and its area computed in km².

**Candidate generation** draws seeds from two independent signals —
depression seeds (cells raised during depression filling by >0.1 m) and
flow-convergence seeds (top-1-percentile flow accumulation) — merges and
declusters them via spatial non-maximum suppression (haversine distance),
then applies three hard filters in sequence before scoring: slope too steep
(>15°), catchment too small (<0.005 km²), and — the newest — **land-use
constraint**: the candidate's point location is checked against a unioned,
buffered set of OpenStreetMap building/road/waterway/water-body/power-line
geometries (buffers: 100 m / 50 m / 30 m / 30 m / 75 m respectively); a
candidate inside any buffer is rejected with a specific reason. Surviving
candidates are scored on five min-max-normalized factors (catchment area
35%, flow accumulation 25%, slope 20%, relief 10%, depression depth 10%)
and ranked.

**Assumptions/limitations** (stated explicitly, per the template's ask):
the land-use filter checks the candidate *point*, not its full catchment
polygon — a catchment naturally spans roads/rivers upstream, which is
hydrologically correct and not filtered; only simple OSM "way" geometries
are handled (complex multipolygon relations are skipped, a documented v1
simplification); DEM resolution (default 30 m) bounds the spatial precision
of every downstream computation.

### 4.3 Rainfall Data Integration

**Open-Meteo's Historical Weather API** (`archive-api.open-meteo.com`) is
queried for daily precipitation at the recommended candidate's coordinates
(or the area's centroid if none is accepted), for a configurable historical
window (default 2015 through the last complete calendar year). Daily values
are aggregated into an annual average, a per-month average across all
covered years, and a monsoon (June–September) seasonal average. This feeds
directly into the Rational Method runoff estimate:
`annual_runoff_m³ = C × annual_rainfall_m × catchment_area_m²`, with
`C = 0.35` by default (documented as representing "mixed agricultural/
semi-pervious land" pending a future soil/land-cover-based refinement), and
pond storage as `storage = annual_runoff_m³ × 0.80` (retention factor),
depth 3.0 m (2.0 m if the candidate's slope exceeds 5°), surface area =
storage / depth.

---

## 5. Implementation

### 5.1 Backend and API Design `[MUST BE INCLUDED]`

| Method & Path | Purpose |
|---|---|
| `POST /api/v1/analyzeContour` | Upload a KML/KMZ contour file → full analysis |
| `POST /api/v1/analyzeArea` | Submit a map-drawn polygon (JSON, no file) → full analysis |
| `GET /api/v1/analysis/{analysis_id}` | Retrieve a previously computed analysis |
| `GET /api/v1/health` | Service health check |

**Authentication**: none (see §2.1 Security NFR).

**Third-party API error handling**: every external call (Open-Meteo, Open-
Elevation, OpenTopoData, Overpass) is wrapped to catch timeout / HTTP-status
/ connection / malformed-payload errors and convert them into a
provider-specific `status: "unavailable"` result with a human-readable
message, rather than propagating an exception — the request still returns
`200 OK` with the rest of the analysis intact plus a `warnings[]` entry.
Internal/validation errors use a consistent `{status, detail,
analysis_id}` JSON error shape across all endpoints (400/404/413/502/500),
enforced by a custom `HTTPException` handler — found and fixed a real
mismatch during development where FastAPI's default handler returned a
different, undocumented shape than what the OpenAPI schema promised.

### 5.2 Frontend and Visualization `[MUST BE INCLUDED]`

React + Leaflet single-page app. Map layers rendered as GeoJSON overlays:
contour lines (upload mode only), candidate points (colour-coded by
status — green accepted, red/muted rejected, with a distinct larger marker
for rank 1), catchment boundary polygons, and a gold recommended-location
marker, each with a popup showing its own stats. Base map is standard
OpenStreetMap raster tiles (dark theme applies a CSS colour-invert filter to
the *same* tiles rather than switching source — see §9 for why), plus an
Esri World Imagery satellite option. The results panel surfaces status,
warnings, the recommended pond's location/catchment/**expected annual water
volume**/planned storage (the three fields the assignment's Phase 3
explicitly requires), supporting rainfall/runoff detail, and collapsible
terrain stats + full candidate table. *(Screenshot placeholder — six real
screenshots from live testing exist in the session's working files and
should be captured here for `Figure~\ref{fig:ui}`.)*

### 5.3 Database and Storage

**Honest answer**: there is no database. Analysis results are held in an
in-memory Python dict (`app/utils/storage.py`), keyed by a UUID
`analysis_id`, and are lost on server restart. This was a deliberate scope
decision for a single-session assignment deployment — the module's own
docstring already documents the upgrade path ("Phase 3 upgrade path:
replace `_store` and the functions below with PostgreSQL+PostGIS calls; the
service and API layers do not change"), i.e. swapping in a real database
is an isolated, additive change, not a rearchitecture. Spatial data
(contours, candidates, catchment polygons) is never persisted at rest —
each request recomputes everything from the input file/polygon and live
external API calls.

---

## 6. CSD Themes and Topics Applied `[MUST BE INCLUDED]`

| CSD Theme/Topic | Where used | Justification |
|---|---|---|
| **API Design (REST)** | 4 versioned endpoints under `/api/v1`, FastAPI auto-generated OpenAPI/Swagger docs at `/docs` | Consistent JSON contract, self-documenting for frontend integration; versioned prefix leaves room for a future `/api/v2` without breaking clients |
| **Caching** | Three independent in-memory caches: rainfall (`rainfall_service.py`, keyed by rounded lat/lon + year range), elevation (`open_elevation.py`, per-point, keyed by rounded lat/lon), land-use (`overpass.py`, per-bbox, **success-only**) | Avoids redundant calls to slow/rate-limited public APIs for overlapping analyses; the "success-only" rule was a real fix — caching a *failure* would otherwise permanently disable that feature for a bbox until process restart, found via live testing |
| **Concurrency / Asynchronous Processing** | (1) `ThreadPoolExecutor` fetches elevation batches in parallel (up to 12 concurrent); (2) `run_in_threadpool` offloads the whole (blocking) analysis pipeline off FastAPI's async event loop | (1) cuts worst-case elevation-fetch time roughly N-fold vs. sequential; (2) fixes a real bug found live: without it, a single slow analysis froze the *entire server*, including unrelated `/health` requests, since the event loop was blocked — verified both before (frozen) and after (an in-flight 30s+ analysis, `/health` still answering in <3ms) |
| **Error Handling and Resilience** | Every external call (4 independent APIs) degrades to `status: "unavailable"` + warning instead of raising; elevation additionally has a two-provider fallback chain and a hard 45s wall-clock deadline | Each of the four dependencies was observed to fail for real during development (DNS failures, rate limits, connection resets, bot-filtering 406s) — this is not a hypothetical concern, it is the normal operating condition observed on the actual deployment network |
| **Algorithms and Complexity** | Priority-Flood depression filling (Barnes et al. 2014, near-linear via min-heap), D8 flow direction (O(cells)), flow accumulation via Kahn's topological sort (O(V+E)), watershed BFS, spatial NMS for candidate declustering | Chosen over naive/quadratic alternatives (e.g. pairwise distance checks, iterative relaxation for depression filling) specifically because the DEM grid can be tens of thousands of cells even for a small village |
| **Design Patterns** | Interchangeable provider modules behind a consistent function interface (elevation: OpenZenith → Open-Elevation → OpenTopoData three-tier fallback; independently, rainfall and land-use each behind their own provider module); orchestrator pattern in `analysis_service.py` coordinating independently-testable stages | New providers can be added/swapped without touching the pipeline that calls them; the orchestrator is "the only component that knows the full pipeline order" (module docstring), keeping every other service independently testable |
| **Testing Strategy** | 70 automated pytest tests (unit: KML parsing, rainfall/runoff/pond services, elevation provider batching/retry/fallback/deadline, land-use categorization/buffering/graceful-degradation; integration: both analysis endpoints end-to-end) + live browser verification (Playwright-driven Chrome) for the frontend, no unit-test framework added there by deliberate scope choice | Gives confidence that resilience behaviour (not just the happy path) is actually correct — several bugs in this project were caught specifically by *live* testing against real external APIs, not by unit tests with mocks |
| **Version Control** | Incremental git commits per fix/feature with descriptive messages documenting root cause, fix, and how it was verified | Keeps the history itself a readable record of what was found and why each change was made, useful for this exact report |
| Load Balancing | *Not implemented* | Single-instance deployment; out of scope at this project's scale |
| Database Indexing / Query Optimization | *Not applicable* | No persistent database exists (see §5.3) |
| Microservices vs. Monolith | Monolith (single FastAPI app) | Deliberate — a distributed-systems split would add operational complexity with no benefit at this scale; the layered `api/services/algorithms/providers` structure already gives clean separation without separate deployables |
| Authentication / Authorization | *Not implemented* | Explicit scope decision (§2.1); would be needed before any public multi-user deployment |
| Containerization / Deployment | *Not yet done* | Open item — see §9 Discussion / next steps |

**Deeper discussion of the two most significant themes**: *Error Handling
and Resilience* and *Concurrency* were the dominant engineering concerns of
this project in practice, not just checklist items. Every one of the four
external APIs this system depends on was observed to genuinely fail during
development — not as a hypothetical edge case, but repeatedly, in real
logs, on the actual deployment network (DNS resolution failures against
Open-Elevation, HTTP 429 rate-limiting from Open-Meteo, HTTP 406 bot-
filtering from the flagship Overpass instance, connection resets from
OpenTopoData). The system's core design principle — every external call
degrades to an explicit "unavailable" status plus a warning rather than
failing the whole request — was validated against real failures, not just
unit-test mocks. Concurrency work followed directly from a bug this
principle surfaced: a single slow, degraded external-API call was found to
freeze the *entire* server (verified live: even `/health` stopped
responding), because the request handler ran inline on the async event
loop. Fixing it (offloading to a thread pool) was necessary specifically
*because* of how failure-prone the external dependencies turned out to be —
without it, "graceful degradation" would still mean "one slow request takes
the whole service down for everyone else in the meantime."

---

## 7. Results and Evaluation `[MUST BE INCLUDED]`

### Representative example (KML upload path, IIT Bhilai contour dataset)

| Metric | Value |
|---|---|
| Contour lines parsed | 1,355 (elevation range 267.0–298.0 m) |
| DEM grid | 106 × 130 cells @ 30 m resolution (~3.9 × 3.2 km) |
| Average slope | 1.9° |
| Candidate seeds found | 355 depression + 63 flow-convergence → 187 after spatial NMS |
| Candidates scored | 15 (top score 82.8) |
| Accepted / rejected | 5 accepted, 0 rejected (this run) |
| Recommended catchment area | 0.0450 km² |
| Historical rainfall (annual avg, 2015–2025) | 1,385.4 mm |
| Estimated annual runoff | 21,820.05 m³ |
| Planned pond storage | 17,456.04 m³ |
| Recommended depth / surface area | 3.0 m / 5,818.7 m² |
| End-to-end processing time | 1.17 s – 7.22 s across repeated real runs |

### Representative example (KML upload path, land-use filter active — analysis `62376cca-263f-4d81-9fe1-e42cb4b96185`)

The exact same flagship dataset (`contours_1m.kml`) analyzed again on a
run where Overpass succeeded: same 1,355 contour lines, same 106×130 DEM
grid, same terrain — but this time **10 of 15 candidates were rejected
with `rejected_land_use_constraint`** against real OpenStreetMap data,
leaving the same top-5 candidates as the primary example above (C4/C6/C9/
C11/C14, identical scores — confirming the terrain/scoring pipeline is
fully deterministic; only the external API outcome varies run to run).
Processing time: 0.94s.

This run is also a clean, real illustration of this project's central
resilience claim, not a hypothetical: **Overpass succeeded while
Open-Meteo failed in the same request** ("Rainfall data is temporarily
unavailable: unable to reach Open-Meteo"). The response still came back
`"status": "success"` with a complete, correctly land-use-filtered
candidate list — only the rainfall-dependent fields (expected annual
collection, planned storage) were `null`, with an explicit warning
explaining why. Each external dependency degrades independently; a
failure in one never blocks a result that other, healthy dependencies can
still produce.

### Representative example (map-drawn-area path, land-use filter active)

A ~0.6 km² user-drawn polygon over the same region: **675 elevation
samples** fetched (200 required nearest-neighbour fill after provider
retries), **11 candidates** generated, **6 rejected** with status
`rejected_land_use_constraint` (real OpenStreetMap data: 23 roads, 1
waterway, 2 water bodies, 1 power line found in the bbox), **5 accepted**.
Verified visually in the browser: rejected (red) candidate markers line up
directly along real road geometry on the satellite basemap; the recommended
(gold) marker sits in open space away from both the river and all roads.

*(No published ground-truth figures were available to compare against —
noted honestly as a limitation in §9, not fabricated.)*

### 7.1 Performance `[MUST BE INCLUDED]`

| Operation | Observed time |
|---|---|
| KML-upload analysis, end-to-end | 1.17 s – 7.22 s (varies mainly with Open-Meteo response time) |
| Map-drawn-area analysis, real elevation fetch via OpenZenith (primary) | ~675-cell grid: 1 request, <1 s, zero gaps; ~1,900-cell grid: 2 requests, ~2 s total, zero gaps — verified live, no fallback needed |
| Map-drawn-area analysis, best case (cached elevation) | 0.02 s – 0.06 s |
| Map-drawn-area analysis, all elevation providers degraded | up to ~30 s observed (pre-OpenZenith); hard-bounded to a **~70–75 s worst case** by a 45 s elevation-fetch deadline regardless (previously unbounded — a real production log showed **~4 minutes** before that deadline was added) |
| `GET /health` while a 30+ second analysis is concurrently in flight | <3 ms (verified live — proves the event-loop-offload fix works, not just that it should in theory) |
| Overpass land-use query (single combined request per analysis) | ~1–2 s when the mirror is healthy; degrades to a skipped filter + warning within its own bounded retry budget otherwise |

No formal load-testing (many concurrent users) was performed — this is
noted as a limitation in §9, not claimed as tested.

---

## 8. Discussion and Limitations

Honest reflection, not just a features list:

- **The land-use filter checks a point, not a catchment.** A recommended
  pond's catchment boundary can legitimately cross a road or pass near a
  building, because that's the real upstream drainage area — this is
  hydrologically correct, not a bug, but it can visually look like an
  oversight to a first-time viewer of the map (observed directly during
  user testing) and is worth explaining in a demo.
- **External API reliability is the single biggest practical risk to this
  system's usability**, not any algorithmic weakness. During development,
  all five external dependencies failed for real at least once, on the
  actual deployment network. The system's resilience design (graceful
  degradation everywhere) was not a hypothetical "nice to have" — it was
  repeatedly the difference between a working demo and a broken one.
- **Direct testing of each provider, bypassing our backend entirely** (to
  separate "our code" from "the provider itself"), plus researching what's
  publicly known about each one, confirmed the unreliability is inherent
  to these services, not specific to any one network:
  - *OpenZenith*: 2 of 3 quick requests got HTTP 503 with Cloudflare error
    1102 ("Origin Rate Limited"). Its GitHub repo (`aliasfoxkde/OpenZenith`)
    shows a solo-developer hobby project — 1 star, zero issues ever filed —
    deployed on Cloudflare Pages/Workers. The 503s are almost certainly
    default Cloudflare free-tier limits on an unfunded project, not an
    engineered capacity plan; recovers in roughly 60–90 seconds once tripped.
  - *Open-Elevation*: 3 of 3 succeeded but slow (0.8–1.3s per single-point
    lookup). Multiple open GitHub issues on the official repo (#29, #46,
    #33) report the identical symptoms — timeouts, SSL failures, 504s — on
    the public instance; the maintainers themselves describe it serving
    "millions of users every day" as a free, donation-funded service, and
    recommend self-hosting for production use.
  - *OpenTopoData*: mostly fine, but a live burst test caught a genuine,
    clean HTTP 429 — matching its documented 1 req/s limit exactly (already
    throttled in this project's code from an earlier fix).
  - *Overpass*: the mirror in use (`maps.mail.ru`) took 13–15 seconds per
    request and one request got no response at all in 15s. It isn't even
    listed on OSM's own Overpass status page — it's an unaffiliated
    third-party proxy, not a community-run instance. Live-testing the two
    commonly-recommended alternatives with a *simple* query found
    `overpass.openstreetmap.fr` answering in ~1 second twice, while
    `overpass.kumi.systems` (reported elsewhere as well-provisioned) timed
    out completely twice — but re-testing with the project's actual,
    heavier combined query (all five feature categories in one request)
    immediately after switching the default turned up a **second, distinct
    root cause**: `overpass.openstreetmap.fr` rejected the real request
    with `HTTP 403 "This service is only available to white-listed
    usages"`, and separately the flagship `overpass-api.de`/`lz4.overpass-
    api.de` instances were still returning their earlier-observed `HTTP
    406` for the same request. Both turned out to be the *same*
    underlying cause: this project's HTTP client was sending httpx's
    generic default User-Agent (`python-httpx/0.27.2`), which multiple
    Overpass operators bot-filter or gate behind exactly the kind of
    "identify yourself" policy the 403 message describes. Adding a
    descriptive `User-Agent` header (`app/utils/http_client.py`, applied
    to every external HTTP call this project makes, not just Overpass)
    immediately fixed both: `overpass.openstreetmap.fr` returned `200 OK`
    in 2.7s, and `lz4.overpass-api.de` in 3.4s, on the identical request
    that was rejected moments earlier. Verified end-to-end afterward: a
    real `/analyzeArea` run completed in 2.09s with the land-use filter
    actually active (2 accepted, 9 rejected) — not skipped. This reframes
    part of the "Overpass is just flaky" narrative: some of what looked
    like provider unreliability this session was this project not
    identifying itself as a client, not the providers themselves being
    down.
  - *Open-Meteo*: 3 of 3 requests hit HTTP 429 — every single attempt, at
    a moment when Open-Meteo's own advertised free-tier limits (600/min,
    10,000/day) should comfortably cover this project's usage (one rainfall
    call per analysis). Open-Meteo's own GitHub issues (#438, #1650)
    describe the same thing happening to other users despite low request
    volume; separately, Render and UiPath both have public reports of
    their platforms' shared outbound IPs getting collectively rate-limited
    by Open-Meteo, because its quota is pooled per-IP across every
    unrelated tenant sharing that egress address — the most plausible
    explanation for hitting this on a university network (or any other
    network sharing a public egress IP with many other users).
  - **Resulting code changes**: a shared, in-memory circuit breaker
    (`app/utils/circuit_breaker.py`) now sits in front of all four
    implemented providers — once one is seen rate-limited (429/503) or
    unreachable, further requests skip it immediately for a cooldown window
    (default 60s) instead of a brand-new request re-discovering the same
    failure from scratch every time, which is exactly what repeated manual
    testing against an already-rate-limited OpenZenith was paying for. A
    descriptive `User-Agent` header (`app/utils/http_client.py`) is now
    sent with every external HTTP call this project makes, fixing the
    bot-filtering/whitelist rejections described above.
  - **Cross-checked against a second opinion (ChatGPT, given only a
    generic description of the problem)**: its suggestions — provider
    abstraction, multi-provider fallback, configurable timeouts, bounded/
    sensible retries, a configurable Overpass URL, graceful degradation
    with explicit per-source warnings — were all already implemented
    earlier this session. Its two genuinely new suggestions (a better
    Overpass mirror, a circuit breaker) are exactly what was added here.
    Its suggestion to add SQLite/Redis caching was deliberately not
    adopted — it conflicts with this project's own already-documented
    scope decision (no database, single-session assignment), and adding a
    persistence layer this close to submission was judged real
    architectural risk for limited benefit at this project's scale. Its
    suggestion to add Open-Meteo-specific rate limiting was also not
    adopted: this project already sends only one rainfall request per
    analysis, so throttling our own call rate further cannot fix a 429
    caused by *other* tenants sharing the same egress IP.
- **A fundamentally different, more robust elevation architecture was
  found by comparing notes with a peer implementation of the same
  assignment**: instead of querying small, free, rate-limited REST APIs,
  it reads **Copernicus DEM GLO-30** directly as Cloud-Optimized GeoTIFF
  tiles hosted as public files on AWS S3 Open Data. This sidesteps the
  entire class of failure documented above — there is no per-request
  quota to exhaust on a static file server; it is not an API call being
  rate-limited, it is a file being read. Verified live before adopting
  it, not assumed: the exact tile-naming convention was guessed and
  confirmed correct on the first try (`Copernicus_DSM_COG_10_N21_00_E081_00_DEM.tif`,
  `HTTP 200`, no credentials needed), the existing `rasterio` dependency
  could open it directly over HTTPS via GDAL's `/vsicurl/` virtual
  filesystem with no new dependency, and the sampled elevation (269 m)
  matched this project's own real KML contour dataset's known range
  (267–298 m) for the same area. Implemented as a new first tier ahead of
  OpenZenith (`app/providers/elevation/copernicus_dem.py`), with the
  existing three-tier REST cascade kept completely intact as the fallback
  for whatever it can't resolve — a pure addition, zero changes to the
  already-tested resilience logic. Verified live end-to-end afterward: a
  real `/analyzeArea` request resolved its entire grid via Copernicus DEM
  alone (no OpenZenith/Open-Elevation/OpenTopoData calls at all), and,
  separately, disabling it via a feature flag confirmed the existing
  cascade still works exactly as before. The same idea applies to
  rainfall (CHIRPS, a similar static-file dataset) but was scoped out of
  this pass — CHIRPS has no pre-computed climatology, so a fresh
  location's multi-year average would need on the order of 130 individual
  monthly file reads, a heavier lift than elevation's one-or-two-tile
  read per analysis, and worth a follow-up rather than bundling in here.
- **A real concurrency bug in the Copernicus DEM tile cache was found from
  a live production log**, not a hypothetical: a larger selected area
  needing more than `ELEVATION_BATCH_SIZE` (1000) grid points splits into
  multiple outer batches that are fetched *concurrently*
  (`fetch_elevations`'s `ThreadPoolExecutor`). Since a selected area's
  whole grid almost always fits inside a single 1°×1° Copernicus DEM
  tile, every one of those concurrent batches needed the *same* tile —
  and the tile cache had no locking, so each batch independently raced to
  open it. The log showed exactly this: one batch's attempt succeeded
  after 14.93 s, while two other batches, racing to open the identical
  tile at the same time, each separately hit a DNS resolution timeout
  after 20 s — wasted, redundant network calls for data one of them had
  already fetched successfully. Fixed with a per-tile lock and
  double-checked-locking pattern (`app/providers/elevation/
  copernicus_dem.py`): the first caller for a given tile opens it; any
  concurrent callers for the *same* tile wait briefly and then reuse its
  result instead of independently re-fetching. A failed open is still not
  cached (matching this project's established "never cache a failure"
  rule), so a genuinely unavailable tile is still retried fresh by the
  next caller rather than permanently blocked. Verified with a dedicated
  concurrency regression test (five threads racing for the same tile
  under a mocked slow open; asserts the underlying open call happens
  exactly once) plus manual review of the fix against the exact log
  sequence that surfaced the bug.
- **Observation from testing on the actual grading/lab machine** (a
  student container, not the development sandbox): *every* external
  dependency — OpenZenith included, which had been perfectly reliable in
  earlier isolated testing — showed real transient failures there (DNS
  resolution failures, connection resets, "network unreachable", gateway
  timeouts), sometimes several within a single request. This confirms the
  unreliability is a property of that network's egress in general, not any
  one provider being uniquely bad, and it directly validated the project's
  resilience-first design approach rather than being a hypothetical
  concern. It also surfaced one genuine bug this way (not found by any
  unit test): when OpenZenith failed a large batch late — after already
  spending much of the shared time budget on its own retries — the
  Open-Elevation/OpenTopoData fallback chain re-chunked that batch into
  many small sub-batches but fetched them *sequentially*, so only the
  first one or two could complete before the deadline. A batch that was
  genuinely recoverable ended up mostly missing, occasionally pushing the
  overall missing-data ratio over the 50% threshold and triggering a false
  "elevation unavailable" error. Fixed by fetching those sub-batches
  concurrently (the same pattern already used elsewhere in the codebase)
  instead of one at a time.
- **A permanent-cache-poisoning bug was found via live testing, not a unit
  test.** The elevation point-cache stored `None` for any point that failed
  every provider tier, exactly as a successful value would be stored — so
  once a bad network moment failed a point, every later request for that
  same area was served the cached failure forever, even after the network
  fully recovered. Caught by noticing an identical failure count (and a
  ~0.06s response time) on a retried request that should have taken tens of
  seconds. Fixed by only caching non-`None` results.
- **DEM padding (10%, avoids flow-routing edge artifacts) meant candidates
  could legitimately render outside the user's drawn rectangle** on the
  map-drawn-area path — including, in one observed run, the *recommended*
  marker itself. Fixed with a `selection_polygon` hard filter: an accepted
  candidate must fall inside the literal drawn polygon, while catchment
  *boundaries* are deliberately left unrestricted, since a real drainage
  basin is not bounded by an arbitrary rectangle.
- **Sequential external calls were found to stack close to the frontend's
  own request timeout.** A real log showed elevation (~65s, including an
  inherent ~15-20s deadline overshoot — an in-flight request already
  launched can't be aborted mid-socket-call) + land-use (~20-40s, previously
  unbounded) + rainfall (~10s) totalling ~117 seconds end-to-end, dangerously
  close to the frontend's 120s abort timeout. Fixed three ways: gave the
  land-use fetch its own hard wall-clock budget (mirroring elevation's),
  launched it concurrently with the elevation fetch (both only need the
  drawn polygon's bbox, not the terrain), and increased the frontend's
  timeout for additional margin.
- **No database** means results don't survive a server restart and there is
  no way to browse past analyses. Acceptable for this assignment's scope;
  the module docstring already documents the intended upgrade path.
- **The runoff coefficient is a single constant** (0.35), not derived from
  actual soil type or land cover — a real accuracy limitation for the
  "expected water volume" figure, explicitly flagged in the UI's assumptions
  section rather than presented as more precise than it is.
- **`leaflet-draw` (the map's polygon/rectangle drawing library) has a
  known upstream bug** in its latest release (1.0.3/1.0.4) that throws a
  console error when drawing a rectangle under modern strict-mode ESM
  bundlers (Leaflet/Leaflet.draw GitHub issue #1026) — worked around by
  pinning to 1.0.2, not by our own code, but worth noting as a third-party
  dependency risk.
- **No load testing was performed.** Concurrency correctness (the event
  loop staying responsive) was verified for a *single* concurrent slow
  request against a fast one, not under many simultaneous users.
- **Coarse DEM resolution** (30 m default, configurable) bounds the spatial
  precision of every downstream computation — a genuinely small terrain
  feature narrower than one cell cannot be represented.

---

## 9. AI Tool Usage Declaration `[MUST BE INCLUDED]`

**Draft — review and personalize before submitting; this is an academic
integrity statement your team signs off on, not something to copy verbatim
without verifying it's accurate to your own experience of the process.**

Claude (Anthropic's Claude Code CLI) was used throughout this project's
Phase 3 backend and frontend implementation, for: architecture planning and
review (proposed changes were presented as an explicit plan and approved
before implementation at each major step); writing backend service/provider
code and frontend components; debugging real failures found through live
testing (including automated browser-driven verification, not only unit
tests); and drafting this report's content from the session's own
implementation record. All AI-generated code was reviewed and iterated on
collaboratively — for example, several real bugs (the event-loop-blocking
freeze, the land-use cache poisoning issue, the CORS credentials
misconfiguration, the invalid empty-coordinates GeoJSON) were found only
because generated code was *actually run and tested* against live external
services rather than accepted on inspection alone, and were fixed with
before/after verification each time. **[Team: state here, honestly, which
parts you personally reviewed most closely / modified further, and confirm
you can explain any part of the codebase if asked — that is the assignment
brief's actual requirement, not just "AI was used."]**

---

## Appendix — Source Code and Repository `[MUST BE INCLUDED]`

- **Repository**: **placeholder** — add the GitHub URL once pushed/public.
- **Folder structure**:
  ```
  backend/
    app/
      api/          — HTTP route handlers (analysis.py, health.py)
      services/      — orchestration (analysis_service.py is the pipeline
                        conductor; one service per concern otherwise)
      algorithms/    — pure computational algorithms (depression fill, D8
                        flow, flow accumulation, watershed, scoring, slope,
                        interpolation)
      providers/     — external API integrations (elevation/, landuse/)
      models/        — dataclasses + Pydantic schemas
      utils/         — geo helpers, GeoJSON, in-memory storage
    tests/           — 70 pytest tests
  frontend/
    src/
      components/    — Header, ModeToggle, UploadPanel, DrawControls,
                        MapView, ResultsPanel, LoadingOverlay, ErrorBanner
      utils/         — format.js (safe display helpers), geojson.js
                        (defensive GeoJSON filtering)
      api.js, theme.js, App.jsx, main.jsx
  ```
- **Final deployed frontend URL**: **placeholder**.
- **Demo video**: **placeholder** (≤5 min, public YouTube link, per phase_03
  requirements).

---

## Still-open items before this can be submitted (tracking, delete before final)

1. Deploy backend + frontend somewhere publicly reachable → fill in the
   "Final Working Front-end URL" requirement.
2. Record and publish the ≤5-minute demo video.
3. Fill in author name(s)/affiliation/email, repository link.
4. Capture real screenshots for Figures (architecture diagram, UI, results
   overlay) — six real ones already exist from live testing this session.
5. Decide whether to add Docker/containerization before writing the CSD
   Themes section's "Containerization" row as anything other than "not
   implemented."
6. Transpose this content into `assignment_info/report_template.tex`,
   respecting the ACM template's formatting (do not change it) and the
   10-page limit — this document is longer than 10 pages of content and
   will need trimming.

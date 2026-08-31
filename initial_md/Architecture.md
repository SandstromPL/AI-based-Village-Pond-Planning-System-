# Backend Architecture

## 1. Architecture Goal

The backend should be designed as a geospatial decision-support system
for village pond planning.

The initial input is a contour map in KML/KMZ format. The backend
progressively transforms this input into:

-   terrain information
-   drainage and catchment information
-   rainfall information
-   runoff estimation
-   pond sizing
-   candidate pond locations
-   a final recommendation

The architecture should remain independent of a particular input file,
elevation provider, or rainfall provider so that the system can be
generalized to other contour maps and data sources.

## 2. Progressive Architecture

The architecture should be developed progressively rather than starting
with a large monolithic pipeline.

### Stage 1 --- Input Layer

``` text
KML / KMZ
   |
   v
File Validation
   |
   v
KML/KMZ Parser
   |
   v
Standard Internal Geospatial Representation
```

The first architectural boundary is between file handling and analysis.
Downstream components should not need to know whether the original file
was KML or KMZ.

### Stage 2 --- Terrain Layer

``` text
Standard Geospatial Data
          |
          v
Terrain Analysis
          |
          +--> elevation statistics
          +--> terrain surface
          +--> slope
          +--> low/high regions
```

The terrain component becomes the foundation for drainage and
candidate-location analysis.

### Stage 3 --- Catchment Layer

``` text
Terrain Model
     |
     v
Drainage Analysis
     |
     +--> flow direction
     +--> flow accumulation
     +--> drainage paths
     +--> catchment / watershed
```

This layer answers:

> If a pond is placed at a particular location, what area naturally
> contributes runoff to it?

### Stage 4 --- External Data Layer

The terrain pipeline can be combined with external data sources.

``` text
             Analysis Engine
              /            \
             v              v
      Elevation Data    Rainfall Data
       provider/API      provider/API
```

The professor-suggested OpenZenith API can be treated as an elevation
provider. Rainfall providers can include sources suggested in the
assignment such as IMD, Open-Meteo, or NASA POWER.

External providers should be hidden behind service/provider interfaces
so they can be replaced later.

### Stage 5 --- Hydrological Layer

``` text
Catchment Area
      +
Rainfall
      +
Runoff assumptions/model
      |
      v
Estimated Runoff Volume
```

This layer converts geospatial and rainfall information into an estimate
of available runoff.

### Stage 6 --- Pond Planning Layer

``` text
Candidate Location
       |
       +--> catchment
       +--> rainfall
       +--> runoff
       +--> terrain
       +--> land constraints
       |
       v
Candidate Score
       |
       v
Recommended Pond Location
       |
       v
Pond Depth / Storage Estimate
```

At this stage, the system becomes a decision-support system rather than
only a terrain-processing API.

### Stage 7 --- Results Layer

The final result should contain both numerical information and
geospatial information.

``` text
Analysis Result
   |
   +--> terrain statistics
   +--> pond location
   +--> catchment boundary
   +--> rainfall statistics
   +--> runoff estimate
   +--> pond dimensions
   +--> recommendation/explanation
```

GeoJSON-compatible output should be preferred for map-based frontend
integration.

## 3. High-Level Architecture

The progressive stages can eventually form this architecture:

``` text
                    Frontend
                       |
                    REST API
                       |
              +--------v---------+
              | FastAPI Backend  |
              +--------+---------+
                       |
       +---------------+----------------+
       |               |                |
       v               v                v
 File/Geo           Terrain         External Data
 Processing         Analysis          Providers
       |               |                |
       +---------------+----------------+
                       |
                       v
              Catchment Analysis
                       |
                       v
                Runoff Analysis
                       |
                       v
               Pond Planning
                       |
                       v
             Scoring/Recommendation
                       |
                       v
                Results / GeoJSON
```

This is a conceptual architecture. Components can initially run inside
one backend process. They do not need to become separate microservices.

## 4. Backend Design Principle

The recommended architecture is modular rather than prematurely
distributed.

Use:

``` text
API layer
   ->
Service layer
   ->
Algorithm layer
   ->
Data/provider layer
```

The HTTP API should not contain the actual terrain or hydrological
algorithms.

For example:

``` text
POST /api/v1/analyze-contour
        |
        v
Analysis Service
        |
        +--> KML Service
        +--> Terrain Service
        +--> Catchment Service
        +--> Rainfall Service
        +--> Runoff Service
        +--> Pond Service
        +--> Scoring Service
```

## 5. Possible Backend Project Structure

This is a proposed structure, not a final implementation decision.

``` text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── analysis.py
│   │   ├── rainfall.py
│   │   └── health.py
│   │
│   ├── services/
│   │   ├── kml_service.py
│   │   ├── terrain_service.py
│   │   ├── catchment_service.py
│   │   ├── rainfall_service.py
│   │   ├── land_service.py
│   │   ├── runoff_service.py
│   │   ├── pond_service.py
│   │   └── scoring_service.py
│   │
│   ├── algorithms/
│   │   ├── interpolation.py
│   │   ├── flow_direction.py
│   │   ├── flow_accumulation.py
│   │   ├── watershed.py
│   │   └── scoring.py
│   │
│   ├── providers/
│   │   ├── elevation/
│   │   │   └── openzenith.py
│   │   └── rainfall/
│   │       ├── open_meteo.py
│   │       └── nasa_power.py
│   │
│   ├── models/
│   │   ├── analysis.py
│   │   ├── terrain.py
│   │   ├── catchment.py
│   │   ├── rainfall.py
│   │   └── pond.py
│   │
│   └── utils/
│
├── data/
├── tests/
├── requirements.txt
└── README.md
```

## 6. Why This Structure

### `api/`

Contains HTTP endpoints only.

### `services/`

Coordinates business logic and combines algorithms/providers.

### `algorithms/`

Contains the actual computational logic, such as interpolation, flow
analysis, watershed calculation, and scoring.

### `providers/`

Contains integrations with external APIs. This prevents
provider-specific code from spreading through the application.

### `models/`

Defines structured inputs and outputs.

### `tests/`

Allows each major component to be tested independently before connecting
the complete pipeline.

## 7. Future Architectural Extensions

The architecture can later support:

-   government/public land datasets
-   satellite imagery
-   soil information
-   land-use/land-cover data
-   road and building layers
-   flood-risk information
-   environmental restrictions
-   asynchronous analysis jobs
-   persistent analysis history
-   multiple elevation/rainfall providers

These should be added as new data providers or services rather than
rewriting the core analysis engine.

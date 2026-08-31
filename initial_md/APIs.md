# Backend APIs

## 1. API Design Philosophy

The backend should distinguish between:

1.  APIs exposed by our application.
2.  Internal service/function interfaces.
3.  External APIs consumed by our backend.

The public REST API should remain relatively small. The complex analysis
should live inside services and algorithms.

------------------------------------------------------------------------

# 2. Application APIs

## 2.1 Analyze Contour

### Endpoint

``` http
POST /api/v1/analyze-contour
```

### Component

File Processing + Analysis Orchestrator

### Input

Multipart file:

``` text
file = village_contour.kml
```

or:

``` text
file = village_contour.kmz
```

### Purpose

Run the complete analysis pipeline.

### Conceptual flow

``` text
Upload
  |
  v
Validate
  |
  v
Parse
  |
  v
Terrain
  |
  v
Catchment
  |
  v
Rainfall
  |
  v
Runoff
  |
  v
Pond Sizing
  |
  v
Scoring
  |
  v
Result
```

### Possible response

``` json
{
  "status": "success",
  "analysis_id": "abc123",
  "terrain": {},
  "candidates": [],
  "recommended_location": {},
  "catchment": {},
  "rainfall": {},
  "runoff": {},
  "pond": {},
  "explanation": []
}
```

------------------------------------------------------------------------

## 2.2 Get Analysis Result

### Endpoint

``` http
GET /api/v1/analysis/{analysis_id}
```

### Component

Results / Analysis Management

### Purpose

Retrieve a previously generated analysis.

Useful if analysis becomes asynchronous or results are stored in a
database.

------------------------------------------------------------------------

## 2.3 Get Catchment Result

### Endpoint

``` http
GET /api/v1/analysis/{analysis_id}/catchment
```

### Component

Catchment Analysis

### Purpose

Return catchment information separately.

Possible output:

``` json
{
  "area_km2": 1.73,
  "boundary": {}
}
```

This is optional. The main analysis endpoint can initially return the
same information.

------------------------------------------------------------------------

## 2.4 Get Rainfall Result

### Endpoint

``` http
GET /api/v1/analysis/{analysis_id}/rainfall
```

### Component

Rainfall Service

### Purpose

Retrieve normalized rainfall information associated with an analysis.

Possible output:

``` json
{
  "annual_average_mm": 1050,
  "monthly": {},
  "seasonal": {}
}
```

------------------------------------------------------------------------

## 2.5 Get Pond Recommendation

### Endpoint

``` http
GET /api/v1/analysis/{analysis_id}/recommendation
```

### Component

Pond Planning / Scoring

### Purpose

Return the recommended candidate and its explanation.

Possible output:

``` json
{
  "location": {
    "latitude": 0,
    "longitude": 0
  },
  "score": 87.4,
  "reasoning": [
    "Large contributing catchment",
    "Suitable terrain",
    "Adequate estimated runoff"
  ]
}
```

------------------------------------------------------------------------

# 3. Optional Development APIs

These endpoints can be useful while developing/testing components
individually. They do not all need to remain in the final public API.

## 3.1 Terrain Analysis

``` http
POST /api/v1/terrain/analyze
```

### Component

Terrain Analysis

### Purpose

Test terrain processing independently of the complete pipeline.

Possible input:

-   contour file

Possible output:

-   elevation statistics
-   slope
-   terrain representation

------------------------------------------------------------------------

## 3.2 Candidate Generation

``` http
POST /api/v1/pond/candidates
```

### Component

Pond Candidate Generation

### Purpose

Generate possible pond locations from terrain information.

------------------------------------------------------------------------

## 3.3 Candidate Scoring

``` http
POST /api/v1/pond/score
```

### Component

Scoring / Recommendation

### Purpose

Test the scoring model independently.

------------------------------------------------------------------------

## 3.4 Runoff Estimation

``` http
POST /api/v1/runoff/estimate
```

### Component

Runoff Service

### Purpose

Test the runoff model using supplied rainfall, catchment, and
assumptions.

------------------------------------------------------------------------

# 4. Internal Service APIs

These are Python interfaces/functions rather than HTTP APIs.

They keep the backend modular.

------------------------------------------------------------------------

## 4.1 KML/KMZ Service

### Component

File Processing

### Possible interface

``` python
parse_contour_file(file_path)
```

### Returns

``` text
NormalizedContourData
```

Responsibilities:

-   detect format
-   extract KMZ contents
-   parse KML
-   extract contour geometries
-   extract elevation
-   normalize coordinates

------------------------------------------------------------------------

## 4.2 Terrain Service

### Component

Terrain Analysis

### Possible interface

``` python
build_terrain_model(contour_data)
```

and:

``` python
analyze_terrain(terrain_model)
```

Possible output:

``` text
TerrainModel
TerrainStatistics
```

------------------------------------------------------------------------

## 4.3 Catchment Service

### Component

Drainage / Catchment

### Possible interface

``` python
calculate_flow_direction(terrain_model)
```

``` python
calculate_flow_accumulation(terrain_model)
```

``` python
calculate_catchment(terrain_model, pond_location)
```

Possible output:

``` text
CatchmentResult
```

------------------------------------------------------------------------

## 4.4 Candidate Service

### Component

Pond Candidate Generation

### Possible interface

``` python
generate_candidates(terrain_model, drainage_data)
```

Possible output:

``` text
List[PondCandidate]
```

------------------------------------------------------------------------

## 4.5 Rainfall Service

### Component

Rainfall

### Possible interface

``` python
get_historical_rainfall(latitude, longitude, start_date, end_date)
```

The service should return normalized project-specific data rather than
provider-specific JSON.

------------------------------------------------------------------------

## 4.6 Runoff Service

### Component

Runoff

### Possible interface

``` python
estimate_runoff(
    rainfall,
    catchment_area,
    runoff_coefficient
)
```

Possible output:

``` text
RunoffResult
```

------------------------------------------------------------------------

## 4.7 Pond Sizing Service

### Component

Pond Planning

### Possible interface

``` python
estimate_pond_size(
    runoff_volume,
    terrain_information
)
```

Possible output:

``` text
PondSizingResult
```

------------------------------------------------------------------------

## 4.8 Scoring Service

### Component

Recommendation

### Possible interface

``` python
score_candidate(
    terrain,
    catchment,
    rainfall,
    runoff,
    land_information
)
```

Then:

``` python
rank_candidates(candidates)
```

------------------------------------------------------------------------

# 5. External APIs

External APIs provide data; they are not APIs built by the project.

------------------------------------------------------------------------

## 5.1 OpenZenith Elevation API

### Component

Terrain / Elevation Provider

### Purpose

Retrieve elevation information for geographic coordinates.

The professor specifically suggested OpenZenith as an elevation API.

Conceptual use:

``` text
latitude + longitude
       |
       v
OpenZenith
       |
       v
Elevation
```

### Recommended architectural role

``` text
ElevationProvider
       |
       +--> OpenZenithProvider
       |
       +--> FutureProvider
```

This keeps the terrain engine independent from OpenZenith.

### Important consideration

Do not make the entire system dependent on OpenZenith if the uploaded
contour map already contains elevation information.

Use it where appropriate for:

-   supplementary elevation data
-   validation
-   filling missing information
-   comparison against the contour-derived terrain model

------------------------------------------------------------------------

## 5.2 Open-Meteo Historical Weather API

### Component

Rainfall Service

### Purpose

Retrieve historical precipitation information for a geographic location.

Potential information:

-   daily precipitation
-   monthly rainfall derived from daily data
-   annual rainfall
-   seasonal rainfall
-   historical statistics

Conceptual flow:

``` text
Candidate Location
       |
       v
Open-Meteo
       |
       v
Historical Rainfall
       |
       v
Normalized Rainfall Data
```

------------------------------------------------------------------------

## 5.3 IMD

### Component

Rainfall Service

### Purpose

Potential source for Indian rainfall information.

Use if the required data/API access is practical for the project.

The assignment explicitly lists IMD as a possible rainfall source.

------------------------------------------------------------------------

## 5.4 NASA POWER

### Component

Rainfall / Environmental Data

### Purpose

Potential source for weather and environmental data.

It can be evaluated as an alternative or supplementary rainfall source.

The assignment lists NASA POWER as a possible rainfall API.

------------------------------------------------------------------------

# 6. Future External Data APIs

These are possibilities rather than requirements for the initial
prototype.

## Satellite Imagery / Map Data

### Component

Mapping / Visualization Data

Potential uses:

-   satellite background
-   village boundary
-   visual validation of candidate location
-   existing water bodies

This mainly supports the frontend but can also provide geospatial
context to backend analysis.

------------------------------------------------------------------------

## Land Use / Land Cover Data

### Component

Land Suitability

Potential uses:

-   agricultural areas
-   built-up areas
-   vegetation
-   water bodies
-   barren land

------------------------------------------------------------------------

## Roads / Buildings

### Component

Land Suitability / Constraints

Potential uses:

-   avoid roads
-   avoid settlements
-   calculate distance from infrastructure

------------------------------------------------------------------------

## Soil Data

### Component

Runoff / Land Suitability

Potential uses:

-   infiltration estimation
-   runoff coefficient refinement
-   excavation suitability

------------------------------------------------------------------------

## Flood / Environmental Data

### Component

Risk / Land Suitability

Potential uses:

-   identify flood-prone areas
-   avoid protected areas
-   identify environmental constraints

------------------------------------------------------------------------

# 7. API-to-Component Mapping

  --------------------------------------------------------------------------------------------
  API / Interface                              Type                    Component
  -------------------------------------------- ----------------------- -----------------------
  `POST /api/v1/analyze-contour`               Public REST             Analysis Orchestrator

  `GET /api/v1/analysis/{id}`                  Public REST             Results

  `GET /api/v1/analysis/{id}/catchment`        Public REST             Catchment

  `GET /api/v1/analysis/{id}/rainfall`         Public REST             Rainfall

  `GET /api/v1/analysis/{id}/recommendation`   Public REST             Pond Recommendation

  `POST /api/v1/terrain/analyze`               Development REST        Terrain

  `POST /api/v1/pond/candidates`               Development REST        Candidate Generation

  `POST /api/v1/pond/score`                    Development REST        Scoring

  `POST /api/v1/runoff/estimate`               Development REST        Runoff

  `parse_contour_file()`                       Internal                KML/KMZ

  `build_terrain_model()`                      Internal                Terrain

  `calculate_flow_direction()`                 Internal                Catchment

  `calculate_flow_accumulation()`              Internal                Catchment

  `calculate_catchment()`                      Internal                Catchment

  `generate_candidates()`                      Internal                Candidate Generation

  `get_historical_rainfall()`                  Internal                Rainfall

  `estimate_runoff()`                          Internal                Runoff

  `estimate_pond_size()`                       Internal                Pond Sizing

  `score_candidate()`                          Internal                Recommendation

  OpenZenith                                   External                Elevation

  Open-Meteo                                   External                Rainfall

  IMD                                          External                Rainfall

  NASA POWER                                   External                Rainfall / Environment
  --------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 8. Recommended Initial Public API

Do not expose every internal function as an HTTP endpoint.

For the first working version, keep the public API simple:

``` text
POST /api/v1/analyze-contour
GET  /api/v1/analysis/{analysis_id}
```

The main endpoint orchestrates the internal services.

During development, temporary component-specific endpoints can be added
for testing.

This keeps the final backend clean while still allowing each component
to be developed independently.

------------------------------------------------------------------------

# 9. Final Analysis Response Concept

A complete analysis can eventually return:

``` json
{
  "analysis_id": "abc123",

  "input": {
    "filename": "sample.kmz",
    "format": "KMZ"
  },

  "terrain": {
    "min_elevation_m": 102.4,
    "max_elevation_m": 148.7,
    "average_slope_percent": 4.8
  },

  "candidates": [
    {
      "id": "C1",
      "location": {},
      "catchment": {},
      "rainfall": {},
      "runoff": {},
      "score": 82.1
    }
  ],

  "recommended_location": {},

  "catchment": {
    "area_km2": 1.73,
    "boundary": {}
  },

  "rainfall": {
    "annual_average_mm": 1050,
    "seasonal_statistics": {}
  },

  "runoff": {
    "estimated_volume_m3": 1250000
  },

  "pond": {
    "recommended_depth_m": 3.5,
    "estimated_storage_m3": 850000
  },

  "explanation": []
}
```

The exact schema should be finalized only after the algorithms and data
models are implemented.

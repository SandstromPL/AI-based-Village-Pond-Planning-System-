# High-Level Design (HLD)

# AI-based Village Pond Planning System

## 1. Document Purpose

This document presents the High-Level Design (HLD) for the **AI-based
Village Pond Planning System**.

The system is a geospatial decision-support web application intended to
help village administrators identify suitable locations for pond
construction by combining:

-   terrain/elevation information
-   contour and catchment analysis
-   rainfall information
-   runoff estimation
-   land and infrastructure constraints
-   pond sizing
-   candidate scoring and recommendation

The design is based on the project requirements, the existing backend
architecture/planning documents, the API design, the component design,
and the agreed **Terrain & Hydrology Algorithm Box**.

The current development approach is progressive: first build a working
backend around the contour input and then add terrain, catchment,
rainfall, runoff, pond sizing, and recommendation stages.

------------------------------------------------------------------------

# 2. Problem Statement

Water conservation is a major challenge in rural areas. Ponds can be
used to harvest and store rainwater, but selecting a suitable location
requires analysis of several geographic and hydrological factors.

A location that is simply low in elevation is not necessarily a good
pond location. A useful location should have:

-   terrain that naturally collects water
-   an adequate contributing catchment
-   suitable slope
-   sufficient rainfall/runoff potential
-   suitable land conditions
-   no unacceptable conflict with rivers, buildings, roads, or other
    constraints
-   sufficient potential storage capacity

The system therefore needs to transform a contour map into meaningful
terrain and hydrological information and then combine that information
with rainfall and other constraints to recommend suitable pond
locations.

The central question of the system is:

> **Where can a pond be placed so that the surrounding terrain can
> naturally collect useful rainfall runoff?**

The conceptual chain is:

``` text
Contour Map
    |
    v
Understand Terrain
    |
    v
Understand Water Movement
    |
    v
Find Catchments
    |
    v
Generate Pond Candidates
    |
    v
Combine Rainfall + Catchment
    |
    v
Estimate Runoff
    |
    v
Estimate Pond Capacity
    |
    v
Rank Candidates
    |
    v
Recommend
```

------------------------------------------------------------------------

# 3. Objectives

## 3.1 Primary Objective

Develop a complete web application capable of analyzing terrain and
rainfall information and recommending suitable locations for village
pond construction.

## 3.2 Specific Objectives

The system should:

1.  Accept contour maps in KML/KMZ format.
2.  Validate and parse uploaded geospatial files.
3.  Extract contour geometries and elevation information.
4.  Convert contour information into a usable terrain representation.
5.  Calculate terrain characteristics such as elevation and slope.
6.  Model the movement of water across the terrain.
7.  Calculate flow direction and flow accumulation.
8.  Identify drainage paths and catchment/watershed regions.
9.  Generate multiple potential pond locations.
10. Estimate the contributing catchment for candidate locations.
11. Retrieve historical rainfall from a public rainfall API.
12. Estimate runoff using rainfall and catchment information.
13. Estimate planning-level pond depth and storage capacity.
14. Consider land, river, road, building, and other constraints where
    reliable data is available.
15. Rank candidate locations using a transparent scoring approach.
16. Provide an explainable recommendation rather than only returning a
    point.
17. Display all important results through an interactive map.
18. Return structured JSON and GeoJSON-compatible geospatial results.
19. Keep the system general enough to process other contour maps without
    hard-coded sample coordinates.

------------------------------------------------------------------------

# 4. Scope

## 4.1 In Scope

The initial system covers:

``` text
KML / KMZ
    |
    v
File Processing
    |
    v
Terrain Analysis
    |
    v
Drainage / Catchment Analysis
    |
    v
Pond Candidate Generation
    |
    v
Rainfall Retrieval
    |
    v
Runoff Estimation
    |
    v
Pond Sizing
    |
    v
Candidate Scoring
    |
    v
Recommendation
    |
    v
Interactive Visualization
```

## 4.2 Future / Optional Scope

The architecture should allow future integration of:

-   government/public land datasets
-   satellite imagery
-   soil information
-   land-use/land-cover
-   road and building layers
-   flood-risk information
-   groundwater information
-   vegetation information
-   protected areas
-   erosion risk
-   additional elevation providers
-   additional rainfall providers
-   asynchronous analysis jobs
-   persistent analysis history

These should be added as new data providers or services instead of
rewriting the core analysis engine.

------------------------------------------------------------------------

# 5. Functional Requirements

The assignment specifies that the application shall support the
following major functions.

  -----------------------------------------------------------------------
  ID                                  Functional Requirement
  ----------------------------------- -----------------------------------
  FR-01                               Display satellite imagery for a
                                      selected village.

  FR-02                               Visualize contour maps.

  FR-03                               Identify available land suitable
                                      for pond excavation.

  FR-04                               Estimate the catchment area
                                      contributing runoff to a selected
                                      location.

  FR-05                               Query historical rainfall data
                                      using publicly available APIs.

  FR-06                               Estimate runoff volume using
                                      rainfall and catchment information.

  FR-07                               Recommend an appropriate pond depth
                                      and approximate storage capacity.

  FR-08                               Overlay pond location, catchment,
                                      rainfall statistics, runoff, pond
                                      dimensions, and other analysis
                                      results.

  FR-09                               Accept KML and KMZ contour files.

  FR-10                               Return structured geospatial
                                      results suitable for frontend
                                      visualization.

  FR-11                               Generate multiple candidate
                                      locations before selecting a final
                                      recommendation.

  FR-12                               Provide an explanation for why the
                                      recommended candidate was selected.
  -----------------------------------------------------------------------

The backend-specific requirements are:

``` text
Accept contour map
       |
       v
Validate
       |
       v
Extract geometry + elevation
       |
       v
Analyze terrain
       |
       v
Estimate catchments
       |
       v
Generate candidates
       |
       v
Retrieve rainfall
       |
       v
Estimate runoff
       |
       v
Estimate pond size
       |
       v
Score candidates
       |
       v
Return recommendation
```

------------------------------------------------------------------------

# 6. Non-Functional Requirements

## 6.1 Generalization

The system must not hard-code:

-   sample map coordinates
-   a particular village
-   a predetermined pond location
-   a predetermined answer

The same processing pipeline should be usable with other contour maps.

## 6.2 Explainability

The recommendation should be explainable.

For example:

``` text
Candidate selected because:
- adequate contributing catchment
- favorable terrain
- sufficient estimated runoff
- acceptable slope
```

The system should expose the major factors behind a candidate score.

## 6.3 Modularity

The following components should be independently testable:

-   file/KML processing
-   terrain analysis
-   catchment analysis
-   rainfall service
-   runoff estimation
-   pond sizing
-   candidate scoring

## 6.4 Provider Independence

External APIs should be hidden behind provider/service interfaces.

For example:

``` text
Rainfall Service
      |
      +---- Open-Meteo
      +---- IMD
      +---- NASA POWER
```

The rest of the application should depend on the normalized rainfall
service rather than a provider-specific response format.

## 6.5 Robustness

The backend should handle:

-   invalid KML
-   invalid KMZ
-   malformed geometries
-   missing elevation information
-   unsupported coordinate systems
-   insufficient terrain information
-   external API failures
-   incomplete input data

## 6.6 Reproducibility

The analysis should record the assumptions and parameters used to
generate a result.

This is particularly important for:

-   terrain-grid resolution
-   hydrological thresholds
-   runoff assumptions
-   candidate scoring parameters
-   external data source/provider

------------------------------------------------------------------------

# 7. Overall System Architecture

## 7.1 High-Level Block Diagram

``` text
                              USER
                               |
                               v
                    +---------------------+
                    |      FRONTEND       |
                    |                     |
                    | Upload KML/KMZ      |
                    | Interactive Map     |
                    | Result Dashboard    |
                    +----------+----------+
                               |
                             REST
                               |
                               v
                    +---------------------+
                    |    FASTAPI BACKEND  |
                    |                     |
                    | API / Orchestrator  |
                    +----------+----------+
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
+--------------+      +------------------+      +------------------+
| File / KML   |      | Terrain &        |      | External Data    |
| Processing   |      | Hydrology Engine |      | Providers        |
+------+-------+      +--------+---------+      +--------+---------+
       |                       |                         |
       |                       |                         |
       |                       |                 +-------+--------+
       |                       |                 |                |
       |                       |                 v                v
       |                       |            Elevation         Rainfall
       |                       |            Provider           Provider
       |                       |
       +-----------+-----------+
                   |
                   v
           Catchment Analysis
                   |
                   v
           Pond Candidate
              Generation
                   |
                   v
             Runoff Analysis
                   |
                   v
             Pond Planning
                   |
                   v
          Candidate Scoring
                   |
                   v
          Recommendation
                   |
                   v
          Results / GeoJSON
                   |
                   v
              Frontend
```

The components can initially run inside one backend process. They do not
need to be deployed as separate microservices.

------------------------------------------------------------------------

# 8. Architectural Layers

The backend follows a modular layered architecture:

``` text
API Layer
    |
    v
Service Layer
    |
    v
Algorithm Layer
    |
    v
Data / Provider Layer
```

## 8.1 API Layer

Responsible for:

-   receiving HTTP requests
-   validating request structure
-   handling file uploads
-   returning HTTP responses

The API layer should not contain the actual terrain or hydrological
algorithms.

## 8.2 Service Layer

Responsible for:

-   coordinating business logic
-   connecting multiple algorithms
-   normalizing external data
-   orchestrating the complete analysis

Example:

``` text
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

## 8.3 Algorithm Layer

Responsible for computational logic such as:

-   contour interpolation
-   terrain modelling
-   slope calculation
-   flow direction
-   flow accumulation
-   catchment delineation
-   depression analysis
-   candidate generation
-   candidate scoring

## 8.4 Provider/Data Layer

Responsible for:

-   external elevation APIs
-   external rainfall APIs
-   future land datasets
-   future environmental datasets
-   database access

------------------------------------------------------------------------

# 9. Project Workflow

## 9.1 Complete Workflow

``` text
1. User uploads KML/KMZ
          |
          v
2. File validation
          |
          v
3. KML/KMZ parsing
          |
          v
4. Extract normalized contour data
          |
          v
5. Build terrain representation
          |
          v
6. Calculate terrain properties
          |
          v
7. Calculate flow direction
          |
          v
8. Calculate flow accumulation
          |
          v
9. Identify drainage/depressions
          |
          v
10. Generate candidate locations
          |
          v
11. Delineate catchment for candidates
          |
          v
12. Apply terrain/hydrology filters
          |
          v
13. Retrieve historical rainfall
          |
          v
14. Estimate runoff
          |
          v
15. Estimate pond depth/storage
          |
          v
16. Apply external constraints
          |
          v
17. Score and rank candidates
          |
          v
18. Select recommendation
          |
          v
19. Generate JSON + GeoJSON results
          |
          v
20. Display results on interactive map
```

------------------------------------------------------------------------

# 10. KML/KMZ Input Processing

The raw KML should not be passed directly to the terrain algorithm.

The processing boundary is:

``` text
RAW KML / KMZ
       |
       v
KML/KMZ Processor
       |
       +--> Validate
       +--> Parse
       +--> Extract
       +--> Normalize
       |
       v
Normalized Contour Dataset
       |
       v
Terrain & Hydrology Engine
```

## 10.1 Information Extracted from the KML

The supplied KML contains contour `Placemark` objects with:

-   contour elevation
-   `LineString` geometry
-   longitude/latitude coordinates
-   contour ID in `ExtendedData`

For example:

``` text
Placemark
    |
    +-- name = 277.0
    |
    +-- ExtendedData
    |      |
    |      +-- ID = 0
    |
    +-- LineString
           |
           +-- coordinates
```

The parser converts this into a normalized representation such as:

``` text
Contour
    ID
    Elevation
    Geometry
```

The important terrain information is:

``` text
Contour Geometry
       +
Contour Elevation
       +
Coordinate Reference Information
       +
Analysis Extent
```

KML presentation information such as:

-   style
-   color
-   line width
-   icon
-   polygon fill

is not core terrain information.

------------------------------------------------------------------------

# 11. Terrain & Hydrology Algorithm

The terrain and hydrology processing is treated as a single internal
**Algorithm Box**.

## 11.1 Algorithm Box

``` text
+--------------------------------------------------------------+
|              TERRAIN & HYDROLOGY ENGINE                      |
|                                                              |
| INPUT                                                        |
|  - Normalized contour geometries                             |
|  - Contour elevations                                        |
|  - Coordinate reference information                          |
|  - Analysis extent                                           |
|  - Processing parameters                                     |
|                                                              |
| PROCESS                                                      |
|  Contours                                                    |
|      |                                                       |
|      v                                                       |
|  DEM / Elevation Grid                                        |
|      |                                                       |
|      v                                                       |
|  Terrain Analysis                                            |
|      |                                                       |
|      +--> Elevation statistics                               |
|      +--> Slope                                               |
|      +--> Low/high regions                                   |
|      |                                                       |
|      v                                                       |
|  Hydrological Conditioning                                   |
|      |                                                       |
|      v                                                       |
|  Flow Direction                                               |
|      |                                                       |
|      v                                                       |
|  Flow Accumulation                                            |
|      |                                                       |
|      v                                                       |
|  Drainage Network                                             |
|      |                                                       |
|      v                                                       |
|  Depression / Low-point Analysis                             |
|      |                                                       |
|      v                                                       |
|  Candidate Generation                                         |
|      |                                                       |
|      v                                                       |
|  Catchment Delineation                                       |
|      |                                                       |
|      v                                                       |
|  Terrain / Hydrology Filtering                               |
|                                                              |
| OUTPUT                                                       |
|  - DEM / terrain information                                 |
|  - slope and terrain statistics                              |
|  - flow direction                                             |
|  - flow accumulation                                          |
|  - drainage information                                      |
|  - depression information                                    |
|  - candidate locations                                       |
|  - catchment boundaries and areas                            |
|  - candidate metadata                                        |
+--------------------------------------------------------------+
```

------------------------------------------------------------------------

# 12. Algorithm / Methodology

## 12.1 Contour Interpolation

A contour map is not automatically a DEM.

The contour lines must first be converted into a terrain representation.

Possible approaches discussed are:

### TIN

A Triangulated Irregular Network represents the terrain using triangles.

``` text
Contour points
      |
      v
   Triangulation
      |
      v
Terrain surface
```

### Raster Interpolation

A regular elevation grid can be generated:

``` text
Contour data
     |
     v
Interpolation
     |
     v
DEM / Grid
```

A raster grid is attractive for the project because it naturally
supports:

-   flow direction
-   flow accumulation
-   drainage
-   depression analysis
-   watershed/catchment analysis

The final interpolation method should be selected after testing the
actual contour dataset.

------------------------------------------------------------------------

# 13. Grid / Neighbour Algorithm

The professor's discussed approach can be understood as a grid-based
terrain graph.

The terrain is represented as square cells/nodes:

``` text
+----+----+----+----+
|    |    |    |    |
+----+----+----+----+
|    |    |    |    |
+----+----+----+----+
|    |    |    |    |
+----+----+----+----+
```

Each cell receives an elevation value.

Example:

``` text
10   9   8   9   10
 9   7   5   7    9
 8   6   3   6    8
 9   7   5   7    9
10   9   8   9   10
```

The low center can represent a potential depression.

The grid can be interpreted as a graph:

``` text
Grid cell = node

Downhill movement = directed edge
```

Water movement is constrained by elevation:

> Water naturally moves from higher elevation toward lower elevation.

This makes graph traversal relevant to:

-   flow propagation
-   upstream analysis
-   catchment delineation
-   connected drainage regions

------------------------------------------------------------------------

# 14. Flow Direction

A common neighbourhood model is the **D8 / 8-neighbour** model:

``` text
NW   N   NE

 W   X    E

SW   S   SE
```

For each grid cell, the surrounding cells are inspected and the downhill
flow direction is determined.

Conceptually:

``` text
Current Cell
      |
      v
Check neighbours
      |
      v
Determine downhill direction
      |
      v
Create flow relationship
```

The resulting terrain can be treated as a directed graph:

``` text
A -> B -> C
      |
      v
      D -> E
```

------------------------------------------------------------------------

# 15. Depression / Sink Analysis

A low point is not automatically the final pond location.

A depression can be represented as:

``` text
High terrain
      \       /
       \     /
        \___/
        low
```

The algorithm should identify:

-   local minima
-   depression regions
-   potential spill/outlet elevations
-   areas that naturally retain or concentrate water

The concept of a spill elevation is important because water can fill a
depression only until it reaches an outlet.

Hydrological conditioning may require:

-   depression filling
-   depression breaching

This helps avoid false sinks caused by terrain-data noise, interpolation
artifacts, or flat regions.

------------------------------------------------------------------------

# 16. Flow Accumulation

Flow direction answers:

> **Where does water from this cell go?**

Flow accumulation answers:

> **How much upstream terrain contributes water to this cell?**

Conceptually:

``` text
      \  |  /
       \ | /
        \|/
         X
```

The convergence point receives water from multiple upstream cells.

A high flow-accumulation region is therefore potentially useful for
candidate generation.

This is why:

``` text
Lowest elevation
       !=
Best pond location
```

A slightly higher location with a much larger contributing catchment may
be more useful.

------------------------------------------------------------------------

# 17. Catchment Delineation

For a potential pond location, the system should determine the terrain
that naturally drains toward that location.

``` text
                 Candidate
                    X
                 ↗  ↑  ↖
               ↗    ↑    ↖
             ↗      ↑      ↖
          upstream contributing area
```

The output includes:

-   catchment boundary
-   catchment area
-   contributing cells
-   drainage information

Catchment area is critical because it determines the potential amount of
rainfall-derived runoff available to the pond.

Catchment delineation can be understood as an upstream graph traversal
over the flow-direction network.

------------------------------------------------------------------------

# 18. Candidate Generation

The system should generate **multiple candidates**, not immediately
select one.

Potential candidate seeds include:

-   local minima
-   terrain depressions
-   high flow-accumulation cells
-   drainage convergence points
-   suitable low-lying regions
-   locations with sufficiently large contributing catchments

Conceptually:

``` text
Large Terrain Grid
       |
       v
Terrain Analysis
       |
       v
Interesting Locations
       |
       v
Candidate Seeds
       |
       v
Detailed Candidate Evaluation
```

Each candidate can contain:

``` text
Candidate
    |
    +-- location
    +-- elevation
    +-- slope
    +-- flow accumulation
    +-- depression information
    +-- catchment area
    +-- catchment boundary
    +-- drainage characteristics
```

------------------------------------------------------------------------

# 19. Hard Constraints vs. Candidate Scoring

These should remain conceptually separate.

## 19.1 Hard Filters

A candidate is unacceptable and should be rejected.

Examples:

-   existing river/water body conflict
-   excessive slope
-   insufficient minimum catchment
-   prohibited land-use area
-   direct infrastructure conflict
-   invalid terrain

``` text
All Candidates
      |
      v
Hard Constraints
      |
      +----> Rejected
      |
      v
Valid Candidates
```

## 19.2 Soft Criteria

A candidate is possible but may be better or worse than another.

Possible factors:

-   catchment size
-   rainfall
-   runoff
-   terrain suitability
-   slope
-   drainage characteristics
-   land suitability

``` text
Valid Candidates
      |
      v
Scoring
      |
      v
Ranked Candidates
```

A transparent scoring approach is preferred over one opaque formula.

------------------------------------------------------------------------

# 20. River and Existing Water Bodies

The supplied map screenshot shows a river/water feature, but the
provided KML snippet is primarily a contour dataset.

Therefore, the architecture should not assume that the river is encoded
in the contour KML.

Instead:

``` text
Contour KML
     |
     v
Terrain / Hydrology Engine
```

and separately:

``` text
River / Water-body Data
     |
     v
Constraint / Suitability Layer
```

The final candidate evaluation can combine:

``` text
Terrain Candidates
       +
River / Water Constraints
       +
Land Constraints
       |
       v
Valid Pond Candidates
```

A candidate inside an existing water body should be rejected. A suitable
buffer around a river can also be treated as a forbidden or
lower-suitability region.

------------------------------------------------------------------------

# 21. Land Suitability

The assignment explicitly includes identifying available land suitable
for pond excavation.

Potential constraints include:

-   government/public land
-   agricultural/private land
-   residential areas
-   roads
-   existing water bodies
-   restricted/protected areas
-   excavation constraints

If reliable land datasets are not available, the system should not
fabricate land results.

Instead, the architecture should allow land information to be integrated
later.

------------------------------------------------------------------------

# 22. Rainfall Methodology

The rainfall component retrieves historical rainfall for the candidate
region.

Potential rainfall information includes:

-   annual rainfall
-   monthly rainfall
-   seasonal rainfall
-   monsoon rainfall
-   historical average
-   rainfall variability
-   extreme rainfall information where available

Annual rainfall alone may not be sufficient because the timing and
seasonal distribution of rainfall influence pond inflow.

The provider-specific response should be normalized into the project's
own rainfall model.

Potential providers discussed in the project are:

-   Open-Meteo
-   IMD
-   NASA POWER

One provider can be integrated initially, while the provider
architecture remains replaceable.

------------------------------------------------------------------------

# 23. Runoff Estimation

The runoff component combines rainfall and catchment information.

A basic conceptual model is:

``` text
Runoff ≈ Rainfall × Catchment Area × Runoff Coefficient
```

The actual calculation must handle:

-   units
-   rainfall period
-   catchment area
-   runoff coefficient
-   losses

Rainfall is not equal to pond inflow because some water:

-   infiltrates
-   evaporates
-   is retained
-   is otherwise lost

Possible future improvements include:

-   soil type
-   land use
-   slope
-   rainfall intensity
-   infiltration
-   antecedent moisture

------------------------------------------------------------------------

# 24. Pond Sizing

The pond-planning component converts estimated available runoff into
planning-level dimensions.

Expected outputs include:

-   recommended depth
-   estimated storage capacity
-   approximate surface area
-   approximate dimensions

Conceptually:

``` text
Catchment
   +
Rainfall
   |
   v
Runoff
   |
   v
Available Water
   |
   v
Storage Requirement
   |
   v
Pond Dimensions
```

These are **planning-level estimates**, not final civil-engineering
designs.

------------------------------------------------------------------------

# 25. Candidate Scoring and Recommendation

Each valid candidate can be scored using information from the preceding
components.

Possible factors include:

-   terrain suitability
-   catchment size
-   rainfall
-   estimated runoff
-   land suitability
-   slope
-   drainage characteristics
-   constraints

Conceptually:

``` text
Terrain Score
      +
Catchment Score
      +
Rainfall Score
      +
Runoff Score
      +
Land Score
      +
Constraint Score
      |
      v
Final Candidate Score
```

The system should return:

1.  ranked candidate list
2.  best candidate
3.  score
4.  explanation/reasoning

The recommendation should remain explainable.

------------------------------------------------------------------------

# 26. Why a Transparent Geospatial Algorithm Is Preferred Initially

Although the project is described as an AI-based system, the
terrain-processing component does not need to be a neural-network model.

A transparent combination of:

``` text
Geospatial algorithms
+
Grid/graph algorithms
+
Hydrological analysis
+
Runoff modelling
+
Candidate scoring
```

is easier to test and explain.

The system should be able to answer:

``` text
Why was Candidate A selected?

Because:
    - contributing catchment is adequate
    - terrain is favorable
    - estimated runoff is sufficient
    - slope is acceptable
    - no major constraint was detected
```

This is particularly important because the assignment requires students
to understand and explain their algorithms and design decisions.

------------------------------------------------------------------------

# 27. Proposed Technology Stack

The assignment allows implementation choices and suggests Python,
Flask/FastAPI, OpenCV, MongoDB/PostgreSQL, elevation APIs, rainfall
APIs, and a basic frontend library.

The current project direction is:

  -------------------------------------------------------------------------
  Layer                   Proposed Technology     Purpose
  ----------------------- ----------------------- -------------------------
  Frontend                React                   Interactive web
                                                  application

  Map visualization       Leaflet                 Interactive map, markers,
                                                  polygons,
                                                  contour/catchment
                                                  overlays

  Backend                 Python + FastAPI        REST API and
                                                  orchestration

  Validation/API models   Pydantic                Request/response
                                                  validation

  Geospatial vectors      GeoPandas               Geospatial data
                                                  processing

  Geometry operations     Shapely                 Geometry parsing and
                                                  spatial operations

  CRS/projection          pyproj                  Coordinate reference and
                                                  projection handling

  Geospatial I/O          GDAL/Fiona              KML/KMZ and geospatial
                                                  file handling

  Raster processing       rasterio                DEM/raster operations

  Numerical processing    NumPy                   Grid and numerical
                                                  computation

  Scientific processing   SciPy                   Numerical/interpolation
                                                  support where required

  Terrain/hydrology       GDAL / WhiteboxTools /  Flow, watershed, terrain
                          suitable hydrology      operations
                          library                 

  Database                PostgreSQL + PostGIS    Persistent relational and
                                                  geospatial storage

  Elevation API           OpenZenith              External elevation
                                                  source/validation where
                                                  required

  Rainfall API            Open-Meteo initially;   Historical rainfall
                          IMD/NASA POWER as       
                          alternatives            

  Data format             JSON + GeoJSON          API and map-compatible
                                                  results

  API documentation       FastAPI/OpenAPI         Interactive API
                                                  documentation

  Testing                 Python testing          Unit/integration testing
                          framework               
  -------------------------------------------------------------------------

### Technology-selection note

Some choices remain implementation decisions and should be finalized
after testing the sample data.

In particular:

-   exact contour interpolation method
-   exact hydrological library
-   exact rainfall provider
-   whether a database is needed in the first prototype
-   final frontend mapping library

The architecture should remain independent of these choices.

------------------------------------------------------------------------

# 28. Database Design

A geospatially capable relational database is preferred for the
long-term architecture.

## 28.1 Proposed Database

``` text
PostgreSQL
     +
PostGIS
```

This supports both standard relational data and geospatial objects.

## 28.2 Conceptual Entities

``` text
Analysis
   |
   +-- Input File
   |
   +-- Terrain Result
   |
   +-- Catchment Result
   |
   +-- Rainfall Result
   |
   +-- Runoff Result
   |
   +-- Pond Candidates
   |
   +-- Recommendation
```

A candidate can conceptually contain:

``` text
Candidate
    candidate_id
    analysis_id
    location
    elevation
    slope
    flow_accumulation
    catchment_area
    catchment_boundary
    rainfall
    runoff
    pond_depth
    storage_capacity
    score
    status
    explanation
```

The exact schema should be finalized alongside implementation.

For a lightweight prototype, persistent database storage can be reduced
or temporarily replaced with local storage, but the service architecture
should not depend on that decision.

------------------------------------------------------------------------

# 29. API Design

## 29.1 API Design Philosophy

The system distinguishes between:

1.  public APIs exposed by the application
2.  internal service/function interfaces
3.  external APIs consumed by the backend

The public REST API should remain relatively small.

Complex analysis should remain inside services and algorithms.

------------------------------------------------------------------------

# 30. Major Public API Endpoints

## 30.1 Analyze Contour

``` http
POST /api/v1/analyze-contour
```

### Purpose

Run the complete analysis pipeline.

### Input

Multipart upload:

``` text
KML file
or
KMZ file
```

### Conceptual processing

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

### Response

A complete analysis result containing:

-   analysis ID
-   input metadata
-   terrain information
-   candidates
-   recommended location
-   catchment
-   rainfall
-   runoff
-   pond sizing
-   explanation
-   geospatial result layers

------------------------------------------------------------------------

## 30.2 Get Analysis Result

``` http
GET /api/v1/analysis/{analysis_id}
```

### Purpose

Retrieve a previously generated analysis.

This is useful when results are stored persistently or the analysis is
later changed to an asynchronous workflow.

------------------------------------------------------------------------

## 30.3 Get Catchment Result

``` http
GET /api/v1/analysis/{analysis_id}/catchment
```

### Purpose

Return catchment information separately.

Possible information:

``` text
catchment area
catchment boundary
drainage information
```

This endpoint is optional in the first public API version because the
main analysis endpoint can return the same information.

------------------------------------------------------------------------

## 30.4 Get Rainfall Result

``` http
GET /api/v1/analysis/{analysis_id}/rainfall
```

### Purpose

Return normalized rainfall information associated with an analysis.

Possible information:

``` text
annual average
monthly rainfall
seasonal rainfall
historical statistics
```

------------------------------------------------------------------------

## 30.5 Get Pond Recommendation

``` http
GET /api/v1/analysis/{analysis_id}/recommendation
```

### Purpose

Return the recommended candidate and explanation.

Possible information:

``` text
location
score
reasoning
pond sizing
catchment
runoff
```

------------------------------------------------------------------------

# 31. Development / Testing APIs

These endpoints are useful for testing components independently and do
not all need to remain in the final public API.

## Terrain

``` http
POST /api/v1/terrain/analyze
```

Purpose:

-   test terrain processing
-   return elevation statistics
-   return terrain representation
-   test slope calculation

## Pond Candidates

``` http
POST /api/v1/pond/candidates
```

Purpose:

-   generate potential pond locations
-   test candidate generation independently

## Candidate Scoring

``` http
POST /api/v1/pond/score
```

Purpose:

-   test candidate scoring independently

## Runoff

``` http
POST /api/v1/runoff/estimate
```

Purpose:

-   test runoff calculations using rainfall, catchment, and assumptions

------------------------------------------------------------------------

# 32. Internal Service Interfaces

These are internal Python interfaces rather than public HTTP endpoints.

Conceptually:

``` text
parse_contour_file()
        |
        v
NormalizedContourData
```

``` text
build_terrain_model()
        |
        v
TerrainModel
```

``` text
calculate_flow_direction()
calculate_flow_accumulation()
calculate_catchment()
        |
        v
CatchmentResult
```

``` text
generate_candidates()
        |
        v
List[PondCandidate]
```

``` text
get_historical_rainfall()
        |
        v
NormalizedRainfallData
```

``` text
estimate_runoff()
        |
        v
RunoffResult
```

``` text
estimate_pond_size()
        |
        v
PondSizingResult
```

``` text
score_candidate()
rank_candidates()
        |
        v
Recommendation
```

The exact function signatures are an implementation detail and are
intentionally not part of this HLD.

------------------------------------------------------------------------

# 33. External APIs

External APIs provide data to the system.

## 33.1 Elevation

### OpenZenith

Role:

``` text
Latitude + Longitude
        |
        v
Elevation Provider
        |
        v
Elevation Data
```

OpenZenith can be used as an elevation provider or validation source.

It should supplement the uploaded contour analysis rather than replace
it.

## 33.2 Rainfall

Possible providers:

``` text
Open-Meteo
IMD
NASA POWER
```

The backend should hide provider-specific response formats behind the
rainfall service.

------------------------------------------------------------------------

# 34. API Result Structure

A complete analysis should conceptually contain:

``` text
Analysis Result
    |
    +-- analysis_id
    |
    +-- input
    |     +-- filename
    |     +-- format
    |
    +-- terrain
    |     +-- min elevation
    |     +-- max elevation
    |     +-- slope
    |
    +-- candidates
    |
    +-- recommended_location
    |
    +-- catchment
    |     +-- area
    |     +-- boundary
    |
    +-- rainfall
    |     +-- annual statistics
    |     +-- seasonal statistics
    |
    +-- runoff
    |     +-- estimated volume
    |
    +-- pond
    |     +-- depth
    |     +-- storage
    |     +-- dimensions
    |
    +-- explanation
    |
    +-- GeoJSON-compatible layers
```

JSON should carry attributes and GeoJSON-compatible structures should
carry map geometries.

------------------------------------------------------------------------

# 35. Frontend Workflow

The frontend should act as the visualization and user-interaction layer.

Conceptually:

``` text
User
 |
 +--> Upload KML/KMZ
 |
 +--> Start analysis
 |
 +--> View contour map
 |
 +--> View terrain
 |
 +--> View catchment
 |
 +--> View candidate locations
 |
 +--> View rainfall
 |
 +--> View runoff
 |
 +--> View pond dimensions
 |
 +--> View recommendation
```

The map can display:

-   satellite imagery
-   contour lines
-   candidate points
-   recommended pond location
-   catchment boundary
-   drainage network
-   other relevant geospatial layers

The frontend should not implement the terrain/hydrological algorithms.

------------------------------------------------------------------------

# 36. Expected Challenges and Proposed Solutions

## 36.1 Challenge --- Contour KML Is Not a DEM

### Problem

The input contains contour lines rather than a ready-to-use elevation
grid.

### Solution

Convert contour geometry + elevation into a terrain surface/DEM-like
representation using an appropriate interpolation approach.

------------------------------------------------------------------------

## 36.2 Challenge --- Large Terrain Grid

### Problem

A very fine grid over a large area can create a large computational
workload.

### Solution

Use an appropriate analysis resolution and avoid unnecessary processing
at extremely fine resolution.

Candidate generation should also reduce the number of locations
requiring detailed analysis.

------------------------------------------------------------------------

## 36.3 Challenge --- Noisy or Artificial Depressions

### Problem

Interpolation or source data can create false sinks.

### Solution

Use hydrological conditioning such as depression filling/breaching and
validate the resulting drainage network.

------------------------------------------------------------------------

## 36.4 Challenge --- Flat Terrain / Equal Elevations

### Problem

Several neighbouring cells can have equal or nearly equal elevation,
making flow direction ambiguous.

### Solution

Handle flat regions explicitly and use a consistent hydrological
conditioning/flow-resolution strategy.

------------------------------------------------------------------------

## 36.5 Challenge --- Lowest Point Is Not Always the Best Location

### Problem

A low point may have little contributing area or may be unsuitable.

### Solution

Use multiple signals:

``` text
Depression
+
Flow Accumulation
+
Catchment
+
Slope
+
Terrain
```

and generate multiple candidates before scoring them.

------------------------------------------------------------------------

## 36.6 Challenge --- River and Existing Water Bodies

### Problem

The map can contain existing rivers/water bodies that should not
automatically become pond candidates.

### Solution

Treat river/water-body information as a separate constraint layer and
reject or penalize candidates that conflict with it.

------------------------------------------------------------------------

## 36.7 Challenge --- Coordinate Systems

### Problem

The KML uses geographic coordinates, while area, distance, and slope
calculations require appropriate spatial units.

### Solution

Detect/maintain CRS information and transform data into a suitable
projected coordinate system before metric calculations.

------------------------------------------------------------------------

## 36.8 Challenge --- External API Failure

### Problem

Rainfall or elevation providers may be unavailable or return incomplete
data.

### Solution

Use provider modules, validation, timeouts/error handling, and a
replaceable provider architecture.

Do not silently fabricate missing external data.

------------------------------------------------------------------------

## 36.9 Challenge --- Rainfall Does Not Equal Runoff

### Problem

Using total rainfall directly as pond inflow would overestimate
available water.

### Solution

Use a runoff model that includes catchment area and a runoff coefficient
or more detailed hydrological assumptions.

------------------------------------------------------------------------

## 36.10 Challenge --- Land Data Availability

### Problem

The assignment requires land suitability, but reliable land
ownership/use datasets may not always be available.

### Solution

Keep land suitability as a modular component. Integrate reliable
datasets when available and explicitly mark unavailable information
rather than inventing results.

------------------------------------------------------------------------

## 36.11 Challenge --- Choosing Arbitrary Thresholds

### Problem

Hard-coded slope, catchment, or suitability thresholds can make the
recommendation unreliable.

### Solution

Keep thresholds explicit and configurable. Record them with the analysis
so the result is reproducible and explainable.

------------------------------------------------------------------------

## 36.12 Challenge --- Computationally Expensive Complete Analysis

### Problem

Terrain, flow, catchment, rainfall, and candidate analysis can be
computationally expensive.

### Solution

Develop progressively:

``` text
KML Parser
    |
    v
Terrain
    |
    v
Catchment
    |
    v
Candidates
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
```

Test each component independently before integrating the complete
pipeline.

If needed later, the architecture can support asynchronous analysis
jobs.

------------------------------------------------------------------------

# 37. Progressive Development Plan

The project should not start as one large monolithic algorithm.

## Phase A --- File Processing

``` text
Upload KML/KMZ
       |
       v
Parse
       |
       v
Extract contours/elevation
       |
       v
Return metadata
```

Primary goal:

> Reliable KML/KMZ processing.

## Phase B --- Terrain

Implement and test:

-   contour interpolation
-   terrain surface/grid
-   elevation statistics
-   slope
-   terrain visualization data

## Phase C --- Catchment

Implement and test:

-   flow direction
-   flow accumulation
-   drainage paths
-   watershed/catchment boundaries

## Phase D --- Candidate Locations

Generate multiple candidates and calculate:

``` text
elevation
slope
catchment
drainage characteristics
```

## Phase E --- Rainfall

Integrate one rainfall provider and normalize its response.

## Phase F --- Runoff

Combine:

``` text
rainfall
+
catchment
+
runoff assumptions
```

## Phase G --- Pond Sizing

Estimate:

-   depth
-   surface area
-   storage capacity
-   approximate dimensions

## Phase H --- Candidate Ranking

Rank candidates and select the best recommendation.

Return both:

``` text
Best candidate
+
Ranked candidate list
```

------------------------------------------------------------------------

# 38. Backend Component Summary

``` text
+---------------------------------------------------------+
|                    FASTAPI BACKEND                      |
|                                                         |
|  API / Orchestrator                                     |
|       |                                                 |
|       +--> KML/KMZ Processing                           |
|       |       |                                         |
|       |       +--> Normalized Contours                 |
|       |                                                 |
|       +--> Terrain Service                              |
|       |       |                                         |
|       |       +--> DEM / Slope / Terrain               |
|       |                                                 |
|       +--> Catchment Service                            |
|       |       |                                         |
|       |       +--> Flow Direction                       |
|       |       +--> Flow Accumulation                    |
|       |       +--> Watershed                            |
|       |                                                 |
|       +--> Candidate Service                            |
|       |       |                                         |
|       |       +--> Candidate Locations                  |
|       |                                                 |
|       +--> Rainfall Service                             |
|       |       |                                         |
|       |       +--> Historical Rainfall                  |
|       |                                                 |
|       +--> Runoff Service                               |
|       |       |                                         |
|       |       +--> Runoff Volume                        |
|       |                                                 |
|       +--> Pond Service                                 |
|       |       |                                         |
|       |       +--> Depth / Storage / Dimensions         |
|       |                                                 |
|       +--> Scoring Service                              |
|               |                                         |
|               +--> Ranking / Recommendation             |
|                                                         |
+---------------------------------------------------------+
```

------------------------------------------------------------------------

# 39. Complete End-to-End Architecture

``` text
                             USER
                              |
                              v
                    +--------------------+
                    |     FRONTEND       |
                    |                    |
                    | Upload / Map / UI  |
                    +---------+----------+
                              |
                              | REST API
                              v
                    +--------------------+
                    |      FASTAPI       |
                    | API + Orchestrator |
                    +---------+----------+
                              |
                              v
                    +--------------------+
                    | KML / KMZ PROCESS  |
                    +---------+----------+
                              |
                              v
                    Normalized Contours
                              |
                              v
        +===========================================+
        |       TERRAIN & HYDROLOGY ENGINE          |
        |                                           |
        |  Contours                                 |
        |     |                                     |
        |     v                                     |
        |  DEM / Terrain Grid                       |
        |     |                                     |
        |     +--> Elevation / Slope                |
        |     |                                     |
        |     +--> Flow Direction                   |
        |     |                                     |
        |     +--> Flow Accumulation                |
        |     |                                     |
        |     +--> Drainage                         |
        |     |                                     |
        |     +--> Depression Analysis              |
        |     |                                     |
        |     +--> Candidate Generation             |
        |     |                                     |
        |     +--> Catchment Delineation            |
        |     |                                     |
        |     +--> Terrain/Hydrology Filtering      |
        +====================+======================+
                             |
                             v
                     Candidate Results
                             |
             +---------------+----------------+
             |                                |
             v                                v
      Rainfall Provider              Land / River /
             |                       Infrastructure
             v                         Constraints
      Rainfall Statistics                     |
             |                                |
             +---------------+----------------+
                             |
                             v
                     Runoff Estimation
                             |
                             v
                       Pond Sizing
                             |
                             v
                     Candidate Scoring
                             |
                             v
                   Ranked Recommendation
                             |
                             v
                  JSON + GeoJSON Results
                             |
                             v
                         FRONTEND
                             |
                             v
                    Interactive Map
```

------------------------------------------------------------------------

# 40. Final Design Principles

The following principles should guide implementation.

## Principle 1 --- Separate file processing from analysis

``` text
KML/KMZ
  |
  v
Parser
  |
  v
Normalized Geospatial Data
  |
  v
Algorithms
```

## Principle 2 --- Treat terrain as a surface/grid for hydrological analysis

``` text
Contours
    |
    v
DEM / Grid
    |
    v
Terrain + Hydrology
```

## Principle 3 --- Model water movement explicitly

``` text
Elevation
    |
    v
Flow Direction
    |
    v
Flow Accumulation
    |
    v
Catchment
```

## Principle 4 --- Do not equate the lowest point with the best pond

``` text
Lowest point
       !=
Best pond
```

Instead:

``` text
Depression
+
Flow accumulation
+
Catchment
+
Slope
+
Constraints
+
Rainfall
+
Runoff
       |
       v
Candidate Score
```

## Principle 5 --- Separate hard rejection from scoring

``` text
Candidates
    |
    v
Hard Constraints
    |
    v
Valid Candidates
    |
    v
Scoring
    |
    v
Ranking
```

## Principle 6 --- Keep external providers replaceable

``` text
Application
    |
    v
Provider Interface
    |
    +--> Open-Meteo
    +--> IMD
    +--> NASA POWER
```

## Principle 7 --- Return geospatial information, not only numbers

The frontend should receive:

``` text
Points
+
Lines
+
Polygons
+
Statistics
+
Candidate metadata
```

GeoJSON-compatible structures are preferred for map visualization.

## Principle 8 --- Keep the recommendation explainable

The system should be able to communicate why a location was selected.

## Principle 9 --- Build progressively

``` text
Parser
  ↓
Terrain
  ↓
Catchment
  ↓
Candidates
  ↓
Rainfall
  ↓
Runoff
  ↓
Pond Sizing
  ↓
Scoring
  ↓
Recommendation
```

## Principle 10 --- Do not over-engineer the first prototype

The components can initially run inside one FastAPI backend.

The architecture should be modular without prematurely splitting the
project into microservices.

------------------------------------------------------------------------

# 41. Expected Final System Output

For a valid contour input, the intended complete system should
ultimately produce:

``` text
INPUT
    |
    +-- KML/KMZ
    |
    v
ANALYSIS
    |
    +-- Parsed contours
    +-- Terrain surface
    +-- Elevation statistics
    +-- Slope
    +-- Flow direction
    +-- Flow accumulation
    +-- Drainage
    +-- Depression regions
    +-- Candidate locations
    +-- Catchment boundaries
    +-- Catchment areas
    +-- Rainfall statistics
    +-- Estimated runoff
    +-- Pond depth
    +-- Storage capacity
    +-- Candidate scores
    |
    v
FINAL RESULT
    |
    +-- Recommended pond location
    +-- Ranked alternatives
    +-- Catchment map
    +-- Rainfall information
    +-- Runoff estimate
    +-- Pond dimensions
    +-- Explanation
    +-- Interactive map layers
```

The system is therefore designed as a **geospatial decision-support
system**, where the terrain/hydrology algorithm is one major analytical
box inside a larger pipeline rather than the entire application.

------------------------------------------------------------------------

# 42. Summary

The proposed HLD separates the system into clear responsibilities:

``` text
KML/KMZ Processor
        ↓
Normalized Geospatial Data
        ↓
Terrain & Hydrology Engine
        ↓
Candidate Pond Locations
        ↓
Rainfall
        ↓
Runoff
        ↓
Pond Sizing
        ↓
Constraints + Scoring
        ↓
Recommendation
        ↓
Interactive Map + Structured Results
```

The most important design decision is the boundary around the **Terrain
& Hydrology Engine**.

It receives normalized contour information:

``` text
Contour geometry
+
Contour elevation
+
CRS
+
Analysis extent
+
Parameters
```

and produces:

``` text
Terrain
+
Flow
+
Drainage
+
Depressions
+
Catchments
+
Pond candidates
```

The downstream components then use those results to incorporate
rainfall, runoff, land constraints, pond sizing, and candidate ranking.

This provides a modular, explainable, testable, and extensible
foundation for the Village Pond Planning System.

# Backend Plans

## 1. Project Thought Process

The backend should be developed around a central question:

> Where can a pond be placed so that the surrounding terrain can
> naturally collect useful rainfall runoff?

The system should not treat the contour map as the final answer. It is
the starting point for a chain of analysis.

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

## 2. Backend Requirements

### Functional requirements

The backend should:

1.  Accept a contour map upload.
2.  Support KML.
3.  Support KMZ.
4.  Validate uploaded files.
5.  Extract contour geometry and elevation.
6.  Analyze terrain.
7.  Estimate catchment areas.
8.  Identify plausible pond locations.
9.  Retrieve historical rainfall.
10. Estimate runoff volume.
11. Estimate pond depth and storage capacity.
12. Return structured results.
13. Return geospatial data suitable for visualization.
14. Be designed so the same pipeline can process other contour maps.

These requirements align with the assignment's stated functionality
around terrain, catchment, rainfall, runoff, pond sizing, and
visualization.

## 3. Non-Functional Requirements

### Generalization

The algorithm must not hard-code the sample map's coordinates,
locations, or expected answer.

### Explainability

The system should provide reasons for recommendations.

Example:

``` text
Candidate selected because:
- adequate contributing catchment
- favorable terrain
- sufficient estimated runoff
- acceptable slope
```

### Modularity

Terrain, rainfall, runoff, and pond sizing should be independently
testable.

### Provider independence

External APIs should be accessed through provider modules.

### Robustness

The backend should gracefully handle:

-   invalid KML
-   invalid KMZ
-   missing elevation data
-   external API failure
-   incomplete geometries
-   unsupported coordinate systems
-   insufficient terrain information

### Reproducibility

The analysis should record assumptions and parameters used for a result.

------------------------------------------------------------------------

## 4. Proposed Technology Stack

### Backend framework

**FastAPI**

Reasons:

-   Python ecosystem
-   easy file upload
-   REST APIs
-   Pydantic validation
-   automatic API documentation
-   suitable for numerical/geospatial processing

The assignment allows Flask or FastAPI.

### Geospatial processing

Potential stack:

-   GeoPandas
-   Shapely
-   pyproj
-   GDAL/Fiona
-   rasterio

The final selection should be made after testing the sample KML/KMZ.

### Numerical processing

Potential stack:

-   NumPy
-   SciPy

### Terrain / hydrological processing

Potential options:

-   rasterio
-   GDAL
-   WhiteboxTools
-   other watershed/flow-analysis libraries

The simplest reliable option should be selected rather than adding
unnecessary dependencies.

### Database

Possible choices:

-   PostgreSQL + PostGIS for a stronger geospatial architecture
-   MongoDB if the project mainly stores document-like analysis results
-   SQLite for a lightweight prototype

For a serious geospatial backend, PostgreSQL + PostGIS is a strong
long-term option.

### External data

Elevation:

-   OpenZenith, as suggested by the professor
-   potentially other elevation sources later

Rainfall:

-   Open-Meteo
-   IMD
-   NASA POWER

Satellite/map services can be added later for frontend visualization.

------------------------------------------------------------------------

## 5. Progressive Implementation Plan

### Phase A --- File Processing

Goal:

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
Return basic metadata
```

First API:

``` text
POST /api/v1/analyze-contour
```

At this stage, focus on reliable file parsing.

### Phase B --- Terrain

Build:

-   contour interpolation
-   terrain surface/grid
-   elevation statistics
-   slope calculation
-   terrain visualization data

Test thoroughly with the sample contour map.

### Phase C --- Catchment

Build:

-   flow direction
-   flow accumulation
-   drainage paths
-   watershed/catchment boundary

This should be treated as a major algorithmic milestone.

### Phase D --- Candidate Locations

Generate multiple candidate locations.

Do not hard-code a single location.

For each candidate calculate:

``` text
elevation
slope
catchment
drainage characteristics
```

### Phase E --- Rainfall

Integrate one rainfall provider first.

Normalize the response into the project's own rainfall model.

Example:

``` text
RainfallProvider
      |
      v
Normalized Rainfall Data
```

### Phase F --- Runoff

Combine:

``` text
rainfall
+
catchment
+
runoff assumptions
```

to estimate runoff.

### Phase G --- Pond Sizing

Estimate:

-   depth
-   surface area
-   storage capacity
-   approximate dimensions

### Phase H --- Candidate Ranking

Score all candidates and select the best one.

Return both:

``` text
Best candidate
```

and:

``` text
Ranked candidate list
```

This is more informative than returning only one point.

------------------------------------------------------------------------

## 6. Complete Backend Flow

``` text
                    Upload
                      |
                      v
                KML / KMZ
                      |
                      v
             File Validation
                      |
                      v
              Geospatial Parser
                      |
                      v
              Terrain Analysis
                      |
            +---------+---------+
            |                   |
            v                   v
       Elevation            Terrain Grid
            |                   |
            +---------+---------+
                      |
                      v
             Candidate Generation
                      |
                      v
              Catchment Analysis
                      |
              +-------+-------+
              |               |
              v               v
         Catchment Area    Drainage Info
              |
              v
          Rainfall API
              |
              v
        Rainfall Statistics
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
       Best Recommendation
              |
              v
        Structured JSON
        + GeoJSON Layers
```

------------------------------------------------------------------------

## 7. Additional Data to Keep in Mind

The contour map is the primary starting point, but a stronger
pond-planning system can eventually incorporate:

### Rainfall

-   annual rainfall
-   monthly rainfall
-   seasonal rainfall
-   monsoon rainfall
-   historical variability
-   extreme rainfall events

### Terrain

-   elevation
-   slope
-   aspect
-   drainage
-   catchment
-   flow accumulation

### Land

-   government/public land
-   agricultural land
-   residential areas
-   roads
-   existing water bodies

### Environmental information

Possible future additions:

-   soil characteristics
-   infiltration
-   groundwater information
-   flood risk
-   protected areas
-   land-use/land-cover
-   vegetation
-   erosion risk

Not all of these are required for the initial prototype. They should be
treated as future extensions unless reliable data is available.

------------------------------------------------------------------------

## 8. Key Algorithmic Principle

The project should not be:

``` text
Lowest point = pond
```

Instead:

``` text
Generate candidates
       |
       v
Analyze terrain
       |
       v
Analyze catchment
       |
       v
Analyze rainfall
       |
       v
Estimate runoff
       |
       v
Check constraints
       |
       v
Score candidates
       |
       v
Recommend
```

This produces a defensible decision-support system.

------------------------------------------------------------------------

## 9. Initial Success Criteria

The first complete backend milestone should be able to:

``` text
Given:
    sample contour KML/KMZ

Produce:
    parsed contours
    terrain statistics
    candidate locations
    catchment information
    rainfall statistics
    estimated runoff
    pond sizing estimate
    ranked recommendation
    GeoJSON-compatible result
```

The system should achieve this without hard-coded coordinates or
sample-specific answers.

------------------------------------------------------------------------

## 10. Development Strategy

Build and test every component independently before integrating it.

Recommended order:

``` text
1. KML/KMZ parser
2. Terrain model
3. Terrain statistics
4. Catchment algorithm
5. Candidate generation
6. Rainfall integration
7. Runoff model
8. Pond sizing
9. Candidate scoring
10. Complete analysis API
```

The final API should act as an orchestrator rather than containing all
of these algorithms itself.

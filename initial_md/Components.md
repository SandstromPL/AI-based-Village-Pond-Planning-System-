# Backend Components

## 1. File and KML/KMZ Processing

### Responsibility

Accept the uploaded contour map and convert it into a standardized
internal geospatial representation.

### Inputs

-   KML file
-   KMZ file

### Main tasks

-   file validation
-   KML parsing
-   KMZ extraction
-   geometry extraction
-   contour/elevation extraction
-   coordinate extraction
-   coordinate-system handling
-   bounding-box calculation
-   malformed-input detection

### Output

A normalized representation containing:

-   contour geometries
-   elevation values
-   coordinates
-   spatial extent
-   coordinate reference information

### Important insight

The rest of the backend should not directly depend on KML/KMZ. Convert
the file into an internal representation first.

This makes future formats easier to support.

### Possible technologies

-   GeoPandas
-   Shapely
-   pyproj
-   Fiona/GDAL

------------------------------------------------------------------------

## 2. Terrain and Elevation Analysis

### Responsibility

Turn contour information into useful terrain information.

### Main tasks

-   minimum elevation
-   maximum elevation
-   elevation range
-   terrain interpolation
-   elevation surface / DEM-like representation
-   slope calculation
-   terrain gradient
-   identification of low/high regions
-   possible valleys and ridges

### Core challenge

A contour map is not automatically a DEM. Contour lines must be
interpreted or interpolated into a terrain representation suitable for
analysis.

Conceptually:

``` text
Contour Lines
     |
     v
Interpolation
     |
     v
Elevation Surface / Grid
     |
     +--> slope
     +--> gradient
     +--> terrain features
```

### OpenZenith possibility

OpenZenith can be treated as an external elevation provider or
validation source.

It should supplement the system rather than replace the analysis of the
uploaded contour map.

------------------------------------------------------------------------

## 3. Drainage and Catchment Analysis

### Responsibility

Determine how water moves through the terrain and estimate the area
contributing runoff to a pond candidate.

### Main concepts

-   flow direction
-   flow accumulation
-   drainage paths
-   watershed
-   catchment boundary
-   contributing area

### Main question

> If a pond is placed at location X, which part of the terrain naturally
> drains toward X?

### Output

-   catchment area
-   catchment boundary
-   drainage information
-   flow-related raster/vector information

### Importance

This is one of the core algorithmic components of the project.

------------------------------------------------------------------------

## 4. Pond Candidate Generation

### Responsibility

Generate multiple plausible pond locations instead of immediately
selecting one location.

### Candidate characteristics

Potential candidates may be based on:

-   relatively low elevation
-   local terrain depressions
-   drainage convergence
-   sufficiently large contributing catchment
-   reasonable slope
-   terrain suitability

### Flow

``` text
Terrain
  |
  v
Potential Locations
  |
  +--> Candidate A
  +--> Candidate B
  +--> Candidate C
  +--> Candidate D
```

Each candidate can then be evaluated independently.

### Important insight

The lowest point is not automatically the best pond location. A useful
pond needs an appropriate contributing catchment and acceptable terrain
characteristics.

------------------------------------------------------------------------

## 5. Rainfall Service

### Responsibility

Retrieve rainfall information for the area surrounding a candidate
location.

### Possible data

-   annual rainfall
-   monthly rainfall
-   seasonal rainfall
-   monsoon rainfall
-   historical average
-   rainfall variability
-   extreme rainfall information where available

### External providers

The assignment suggests:

-   IMD
-   Open-Meteo
-   NASA POWER

Open-Meteo is a practical candidate for an initial implementation.

### Important insight

Annual rainfall alone may not be sufficient. Seasonal distribution
matters because pond inflow depends strongly on when rainfall occurs.

### Output

A normalized rainfall object should hide provider-specific response
formats.

------------------------------------------------------------------------

## 6. Land Suitability

### Responsibility

Determine whether a candidate location is practically suitable for pond
excavation.

### Possible constraints

-   government/public land
-   agricultural/private land
-   residential areas
-   roads
-   existing water bodies
-   restricted/protected areas
-   excavation constraints

### Current implementation strategy

If reliable land datasets are unavailable, do not fabricate results.

Instead design the component so that land data can be added later.

### Importance

The assignment explicitly mentions government land availability and
suitable land for pond excavation.

------------------------------------------------------------------------

## 7. Runoff Estimation

### Responsibility

Estimate how much rainfall becomes runoff reaching the catchment.

### Inputs

-   rainfall
-   catchment area
-   runoff coefficient or hydrological model
-   potentially terrain/land characteristics

### Basic conceptual model

``` text
Runoff ≈ Rainfall × Catchment Area × Runoff Coefficient
```

Unit conversions and assumptions must be handled explicitly.

### Possible future improvements

-   soil type
-   land use
-   slope
-   rainfall intensity
-   infiltration
-   antecedent moisture

### Important insight

Rainfall is not equal to pond inflow. Some rainfall infiltrates,
evaporates, or is otherwise lost.

------------------------------------------------------------------------

## 8. Pond Sizing

### Responsibility

Convert estimated available runoff into planning-level pond dimensions.

### Outputs

-   recommended depth
-   estimated storage capacity
-   approximate pond surface area
-   approximate dimensions

### Flow

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

### Important limitation

These should be described as planning-level estimates, not final
civil-engineering designs.

------------------------------------------------------------------------

## 9. Candidate Scoring and Recommendation

### Responsibility

Rank possible pond locations using the information produced by other
components.

### Possible factors

-   terrain suitability
-   catchment size
-   rainfall
-   estimated runoff
-   land suitability
-   slope
-   drainage characteristics
-   constraints

### Example conceptual score

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

### Important insight

A transparent scoring model is preferable to claiming that an opaque AI
model selected the location.

The system should be able to explain why a candidate received its score.

------------------------------------------------------------------------

## 10. Results and Geospatial Output

### Responsibility

Produce structured results for the frontend.

### Recommended output

Use JSON for attributes and GeoJSON-compatible structures for
geometries.

### Possible output sections

-   input information
-   terrain statistics
-   recommended location
-   candidate locations
-   catchment boundary
-   rainfall statistics
-   runoff estimate
-   pond dimensions
-   recommendation explanation

### Why GeoJSON

The frontend can directly visualize:

-   points
-   polygons
-   contour lines
-   catchment boundaries
-   candidate locations

without needing to understand the backend algorithms.

------------------------------------------------------------------------

## Component Dependency

The major dependency chain is:

``` text
KML/KMZ Processing
        |
        v
Terrain Analysis
        |
        +--------------------+
        |                    |
        v                    v
Catchment Analysis      Candidate Generation
        |                    |
        +----------+---------+
                   |
                   v
             Rainfall Data
                   |
                   v
             Runoff Model
                   |
                   v
              Pond Sizing
                   |
                   v
              Scoring
                   |
                   v
          Recommendation
```

Land suitability can feed into candidate generation, scoring, or both.

------------------------------------------------------------------------

## Components to Prioritize

### Highest priority

1.  KML/KMZ processing
2.  Terrain reconstruction
3.  Catchment analysis
4.  Candidate generation

### Second priority

5.  Rainfall service
6.  Runoff estimation
7.  Pond sizing

### Enhancement

8.  Candidate scoring
9.  Land suitability
10. Additional environmental datasets

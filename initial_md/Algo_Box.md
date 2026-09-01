# Algo Box --- Terrain & Hydrology Processing

## Project Context

The current project is the **AI-based Village Pond Planning System**.
The current development phase is focused on building a working backend
and, specifically, understanding the algorithmic processing that should
happen after a contour KML/KMZ file is received.

The central problem is:

> **Where can a pond be placed so that the surrounding terrain can
> naturally collect useful rainfall runoff?**

The contour map is therefore not the final answer. It is the starting
point for a chain of terrain, hydrological, rainfall, runoff, and
pond-suitability analysis.

The overall conceptual pipeline is:

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

# Part 1 --- Understanding the KML and the Algorithm

## 1.1 What the Given KML Contains

The provided KML represents a contour map.

A simplified structure of the file is:

``` text
Folder
 |
 +-- contours_1.0m
      |
      +-- lines
           |
           +-- Placemark
           |     |
           |     +-- name = 277.0
           |     +-- ExtendedData
           |     +-- LineString
           |           +-- coordinates = longitude, latitude points
           |
           +-- Placemark
           |     |
           |     +-- name = 280.0
           |     +-- LineString
           |           +-- coordinates = longitude, latitude points
           |
           +-- Placemark
                 |
                 +-- name = 274.0
                 +-- LineString
                       +-- coordinates = longitude, latitude points
```

For example, the provided KML contains:

``` text
<Placemark>
    <name>277.0</name>
    ...
    <LineString>
        <coordinates>
            81.2863210276816,21.2635391843863
            81.2863210276816,21.2635184529693
            ...
        </coordinates>
    </LineString>
</Placemark>
```

The important information here is:

``` text
Contour elevation = 277.0 m

Contour geometry =
    ordered sequence of
    longitude/latitude coordinates
```

Other examples in the supplied portion include contour elevations such
as:

``` text
277 m
280 m
274 m
280 m
283 m
...
```

The KML therefore gives us **where each contour line is and what
elevation that contour represents**.

------------------------------------------------------------------------

## 1.2 What Information Is Important for the Algorithm?

The terrain/hydrology algorithm does not need all of the KML
information.

### Important information

The algorithm primarily needs:

1.  **Contour geometry**
    -   The LineString coordinates.
    -   These describe the shape and location of each contour.
2.  **Contour elevation**
    -   The elevation associated with the contour.
    -   In this KML, the elevation is contained in the `<name>` element
        of the Placemark.
3.  **Contour identifier**
    -   The `ID` from `ExtendedData` can be retained for traceability.
4.  **Coordinate reference information**
    -   The coordinates are geographic longitude/latitude values.
    -   The processing pipeline must know the spatial reference/CRS so
        that distance, area, slope, and grid calculations are performed
        appropriately.
5.  **Analysis extent**
    -   The spatial extent/bounding region covered by the contour data.
6.  **Processing parameters**
    -   For example, terrain-grid resolution and other algorithmic
        thresholds.

### Information that is mostly presentation metadata

The following information is not the core terrain input:

``` text
Style
LineStyle
color
width
PolyStyle
Icon
```

These describe how the KML is displayed rather than the physical
terrain.

Therefore, the parser should convert the raw KML into a clean,
normalized terrain representation.

------------------------------------------------------------------------

## 1.3 KML Should Not Be the Direct Input to the Terrain Algorithm

A useful architectural boundary is:

``` text
RAW KML / KMZ
       |
       v
KML/KMZ Processor
       |
       | Parse
       | Validate
       | Extract
       | Normalize
       v
Normalized Contour Dataset
       |
       v
Terrain / Hydrology Algorithm
```

The terrain algorithm should not have to understand XML/KML syntax.

The KML processor answers:

> **What does this file contain?**

The terrain/hydrology algorithm answers:

> **Given these contours, what does the terrain look like and how would
> water move through it?**

------------------------------------------------------------------------

# 1.4 The Major Algorithmic Problem

The KML contains contour lines, but hydrological algorithms are much
easier to perform on an elevation surface or grid.

Therefore the first major transformation is:

``` text
Contour Lines
     |
     v
Elevation Surface / DEM
     |
     v
Terrain Grid
```

For example, imagine a grid covering the area:

``` text
+----+----+----+----+----+
|    |    |    |    |    |
+----+----+----+----+----+
|    |    |    |    |    |
+----+----+----+----+----+
|    |    |    |    |    |
+----+----+----+----+----+
|    |    |    |    |    |
+----+----+----+----+----+
```

Each cell/node receives an estimated elevation:

``` text
+-----+-----+-----+-----+
| 281 | 280 | 279 | 281 |
+-----+-----+-----+-----+
| 280 | 277 | 275 | 279 |
+-----+-----+-----+-----+
| 279 | 275 | 273 | 277 |
+-----+-----+-----+-----+
| 282 | 279 | 276 | 280 |
+-----+-----+-----+-----+
```

This is essentially a DEM-like raster representation.

------------------------------------------------------------------------

# 1.5 Contour Interpolation

There are multiple possible approaches for converting contour
information into an elevation surface.

### Option A --- TIN

A Triangulated Irregular Network can represent the terrain using
triangles created from elevation points:

``` text
Contour points
      |
      v
    points
   / |  \
  /  |   \
 /___|____\
 \   |    /
  \  |   /
   \ |  /
 triangles
```

The triangles form a continuous terrain representation.

### Option B --- Raster interpolation

A regular grid can be created and elevation can be interpolated onto it:

``` text
Contour data
     |
     v
Interpolation
     |
     v
DEM

280 279 278 279 281
279 277 275 277 280
278 275 273 275 279
280 278 276 278 281
```

For this project, a raster DEM/grid is particularly attractive because
the following hydrological operations become easier to represent:

-   flow direction
-   flow accumulation
-   drainage
-   depression analysis
-   catchment/watershed analysis

The final choice of interpolation method should be made after testing
the actual sample KML/KMZ and checking whether the resulting terrain is
reliable.

------------------------------------------------------------------------

# 1.6 The Professor's Grid-and-Neighbour Algorithm Idea

The algorithm discussed in class can be understood as a terrain-grid
approach.

The terrain is represented as a large grid of square cells/nodes.

Each node receives an elevation or relative terrain value.

For example:

``` text
10   9   8   9   10
 9   7   5   7    9
 8   6   3   6    8
 9   7   5   7    9
10   9   8   9   10
```

The center represents a low area:

``` text
10   9   8   9   10
 9   7   5   7    9
 8   6  [3]  6    8
 9   7   5   7    9
10   9   8   9   10
```

The basic intuition is:

> Water naturally moves from higher elevation toward lower elevation.

Therefore, for each grid node, inspect its neighbouring nodes and
determine where water can move next.

This turns the terrain into a graph:

``` text
Each grid cell = node

Downhill movement = directed edge
```

For example:

``` text
A -> B -> C
      |
      v
      D -> E
```

This connects naturally with graph traversal ideas such as those used in
grid/graph problems like connected components or island problems.

------------------------------------------------------------------------

# 1.7 Neighbour Analysis / Flow Direction

A common grid model is the 8-neighbour or D8 neighbourhood:

``` text
NW   N   NE

 W   X    E

SW   S   SE
```

For each cell, the surrounding cells are examined.

Suppose:

``` text
52   51   55
53   50   54
56   52   58
```

For the center cell:

``` text
X = 50
```

the surrounding lower elevation is 51.

Therefore, the flow direction from the center is toward that neighbour.

Conceptually:

``` text
52   51   55
      ^
53   50 -> 54
56   52   58
```

In a complete DEM, this gives each cell a direction toward a lower
neighbour.

------------------------------------------------------------------------

# 1.8 Why We Should Not Simply "Find the Lowest Point"

A simple algorithm could be:

``` text
Find lowest point
       |
       v
Make pond there
```

But this is not sufficient.

The lowest point may:

-   have a very small contributing area
-   be unsuitable for construction
-   be part of an existing river/water body
-   have unsuitable surrounding terrain
-   not receive enough runoff
-   be located in an otherwise unsuitable region

The actual objective is closer to:

> **Find locations where terrain naturally concentrates water and where
> sufficient upstream area contributes runoff.**

Therefore, multiple terrain and hydrological characteristics must be
considered.

------------------------------------------------------------------------

# 1.9 Depression Analysis

Consider a bowl-like terrain:

``` text
       100     100
    95             95
  90       70       90
    85             85
       80     80
```

The center is a depression.

Water entering this region moves toward the low area.

However, water does not necessarily remain there forever.

Eventually it reaches a spill/outlet elevation.

For example:

``` text
Depression minimum = 70 m
Spill elevation     = 85 m
```

The potential ponding region is approximately the terrain enclosed below
the spill elevation.

Conceptually:

``` text
       ┌───────────────┐
       │               │
       │    ╭────╮     │
       │   ╱      ╲    │
       │  │ pond   │   │
       │   ╲      ╱    │
       │    ╰────╯     │
       │               │
       └───────────────┘
```

The rectangular region is useful as a search/bounding region, but the
actual pond boundary should follow the terrain and therefore be
irregular.

------------------------------------------------------------------------

# 1.10 Depression/Sink Handling

Real terrain data can contain:

-   small artificial pits
-   DEM noise
-   flat regions
-   contour interpolation artifacts
-   disconnected contour features

A raw flow-direction algorithm can therefore encounter cells from which
water appears to have nowhere to go.

Two important concepts are:

### Depression filling

Raise trapped terrain cells until the depression has an outlet.

Conceptually:

``` text
Before:

10 10 10
10  5 10
10 10 10


After filling:

10 10 10
10 10 10
10 10 10
```

### Depression breaching

Instead of raising the depression, identify or create an outlet through
the surrounding terrain.

Conceptually:

``` text
      ridge
  ███████████
  █    ↓    █
  █   bowl  █
  █         █
  ███████████
        ↓
      outlet
```

These are important concepts for hydrological conditioning.

The implementation does not necessarily have to be written from scratch;
an established terrain/hydrology library can be used if appropriate.
However, the team should understand the concept because the assignment
requires students to be able to explain their algorithms and design
decisions.

------------------------------------------------------------------------

# 1.11 Flow Accumulation

Flow direction tells us:

> **Where does water from this cell go?**

Flow accumulation asks:

> **How much upstream terrain contributes water to this cell?**

Consider:

``` text
       \  |  /
        \ | /
         \|/
          X
```

Many upstream cells contribute to X.

A flow-accumulation surface might conceptually look like:

``` text
1   1   1   1

1   3   5   1

1   5  15   2

1   2   4   1
```

The cell with value 15 receives water from a large contributing region.

This means a location does not need to be the absolute lowest point to
be useful.

A location where many flow paths converge may be a strong pond
candidate.

------------------------------------------------------------------------

# 1.12 Flow Direction + Flow Accumulation + Depression Analysis

These analyses should be complementary.

### Depression analysis asks:

> Where does terrain naturally hold water?

### Flow accumulation asks:

> Where does water naturally converge?

Therefore:

``` text
             DEM
              |
       +------+------+
       |             |
       v             v
 Depression      Flow Direction
 Analysis             |
       |              v
       |        Flow Accumulation
       |              |
       +------+-------+
              |
              v
       Candidate Locations
```

This is stronger than using only one method.

------------------------------------------------------------------------

# 1.13 Terrain as a Directed Graph

Once flow direction is calculated:

``` text
cell -> downhill neighbour
```

the DEM can be treated as a directed graph.

Example:

``` text
A -> B -> C
    |
    v
    D -> E
        |
        v
        F
```

The graph can be used to determine upstream contributing areas.

For example, if a pond candidate is at F:

``` text
F
^
E
^
D
^
B
^
A
```

The cells that eventually drain toward F form the contributing
catchment.

Therefore:

> **Catchment delineation can be understood as an upstream
> graph-traversal problem over the flow-direction network.**

------------------------------------------------------------------------

# 1.14 Candidate Generation

Do not scan every grid cell and immediately declare it a pond.

Instead, identify interesting locations first.

Possible candidate seeds include:

``` text
Local minima
Depressions
High flow-accumulation cells
Drainage convergence points
```

Conceptually:

``` text
Large terrain grid
       |
       v
Terrain analysis
       |
       v
Interesting locations
       |
       v
Candidate seeds
       |
       v
Detailed evaluation
```

This avoids treating every cell equally.

------------------------------------------------------------------------

# 1.15 Candidate Information

Each candidate should have associated terrain/hydrological information.

Conceptually:

``` text
Candidate 1
    location
    elevation
    slope
    flow accumulation
    depression information
    catchment area
    catchment boundary

Candidate 2
    location
    elevation
    slope
    flow accumulation
    depression information
    catchment area
    catchment boundary
```

The system should generate multiple candidates rather than hard-code a
single location.

------------------------------------------------------------------------

# 1.16 Catchment Delineation

For each candidate, determine which upstream terrain contributes runoff
to that location.

Conceptually:

``` text
                 Candidate A
                      ●
                  ↙   ↓   ↘
                ↙     ↓     ↘
              ↙       ↓       ↘
            upstream contributing terrain
```

The result is a catchment polygon:

``` text
Candidate A
    |
    +-- catchment boundary
    +-- catchment area
    +-- contributing cells
    +-- drainage characteristics
```

The catchment area is important because it determines how much rainfall
can potentially contribute runoff to the pond.

------------------------------------------------------------------------

# 1.17 River and Existing Water Bodies

The supplied screenshot shows a river/water feature.

An important architectural distinction is:

> **Do not assume that the contour KML itself contains the river unless
> the KML actually includes a river/water-body layer.**

The provided KML snippet is clearly showing contour LineStrings. The
river visible on the map may come from another map/data layer.

Therefore:

``` text
Contour KML
     |
     v
Terrain/Hydrology Engine
```

and separately:

``` text
River / Water-body Data
     |
     v
Constraint / Suitability Layer
```

Then:

``` text
Terrain Candidates
       +
River/Water Constraints
       +
Land Constraints
       |
       v
Valid Pond Candidates
```

A candidate inside an existing water body should be rejected.

A buffer around a river can also be used as a forbidden or
lower-suitability zone.

------------------------------------------------------------------------

# 1.18 Hard Filters vs. Scoring

This distinction should be explicit.

## Hard filter

A location is unacceptable.

Example:

``` text
Candidate
    |
    v
Inside existing river/water body?
    |
   YES
    |
    v
REJECT
```

Other possible hard filters:

-   excessive slope
-   invalid terrain
-   unsuitable location
-   insufficient minimum catchment
-   prohibited land/use area
-   direct conflict with existing infrastructure

## Soft criterion

A location is still possible, but one candidate is better than another.

Example:

``` text
Candidate A
catchment = 4.2 km²

Candidate B
catchment = 2.1 km²
```

Candidate A could receive a higher score.

The important architecture is:

``` text
All Candidates
      |
      v
Hard Constraints
      |
      +----> Rejected Candidates
      |
      v
Valid Candidates
      |
      v
Scoring
      |
      v
Ranked Candidates
```

This is preferable to putting every consideration into one large
formula.

------------------------------------------------------------------------

# 1.19 Slope as a Filter

A location may collect water but still be unsuitable if the terrain is
too steep.

Conceptually:

``` text
Candidate A
   ________
__/        \__
gentle terrain

Candidate B
       /
      /
     /
    /
steep terrain
```

Slope can therefore be calculated from the DEM and used as:

``` text
slope > acceptable threshold
        |
        v
      reject
```

The exact threshold should be an explicit project assumption or
supported by appropriate domain reasoning rather than being arbitrarily
selected.

------------------------------------------------------------------------

# 1.20 Catchment Size as a Filter/Score

Suppose:

``` text
Candidate A
catchment = 0.02 km²

Candidate B
catchment = 2.5 km²
```

Candidate B has much more potential contributing area.

A candidate with an extremely small contributing catchment may be
rejected or receive a lower suitability score.

This is another reason why:

``` text
lowest point = pond
```

is not a sufficient algorithm.

------------------------------------------------------------------------

# 1.21 Land and Infrastructure Constraints

Eventually, candidate evaluation can also consider:

``` text
road nearby?
building nearby?
settlement?
protected area?
existing water body?
government/public land?
agricultural land?
```

Some should be hard constraints.

Others should be scoring criteria.

Possible future environmental information includes:

-   soil characteristics
-   infiltration
-   groundwater information
-   flood risk
-   protected areas
-   land-use/land-cover
-   vegetation
-   erosion risk

Not all of these are required for the initial prototype.

------------------------------------------------------------------------

# 1.22 Why the Algorithm Should Not Be an AI/ML Model Initially

The project is called an AI-based pond planning system, but the
terrain-processing component does not need to be a neural network.

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

is more explainable.

The project should be able to explain:

``` text
Candidate selected because:
    adequate contributing catchment
    favorable terrain
    sufficient estimated runoff
    acceptable slope
```

This is much easier to defend during demonstration than an opaque model.

------------------------------------------------------------------------

# 1.23 Recommended Algorithm Inside the Box

The recommended conceptual algorithm is:

``` text
Contours
   |
   v
Contour interpolation
   |
   v
DEM / Elevation Grid
   |
   v
Hydrological conditioning
   |
   v
Flow Direction (D8)
   |
   v
Flow Accumulation
   |
   v
Drainage Network
   |
   +--------------------+
   |                    |
   v                    v
Depression Analysis   Terrain Analysis
   |                    |
   |                    +-- Elevation
   |                    +-- Slope
   |                    +-- Relief
   |
   +---------+----------+
             |
             v
      Candidate Generation
             |
      +------+------+------+
      |      |             |
      v      v             v
   Low     Depressions   Convergence
   points
      |      |             |
      +------+------+------+
             |
             v
      Candidate Locations
             |
             v
      Catchment Delineation
             |
             v
       Hard Constraints
             |
             v
       Valid Candidates
             |
             v
       Candidate Scoring
             |
             v
       Ranked Pond Sites
```

The central principle is:

> **Generate candidates → analyze terrain → analyze catchment → analyze
> rainfall → estimate runoff → check constraints → score candidates →
> recommend.**

This avoids the incorrect assumption:

``` text
Lowest point = pond
```

------------------------------------------------------------------------

# Part 2 --- Treating the Algorithm as a Backend Box

## 2.1 Purpose of the Box

For backend architecture, the entire terrain/hydrology algorithm should
be treated as a black-box component.

The box should have:

``` text
INPUT
   |
   v
┌─────────────────────────────────────┐
│     TERRAIN & HYDROLOGY ENGINE      │
│                                     │
│  Internal terrain/hydrology logic  │
│                                     │
└──────────────────┬──────────────────┘
                   |
                   v
OUTPUT
```

The rest of the backend should not need to know the internal
implementation details of the algorithm.

------------------------------------------------------------------------

# 2.2 What Goes Into the Box?

The box should **not receive the raw KML**.

The raw file first goes through:

``` text
KML/KMZ Processor
```

which performs:

``` text
Validate
Parse
Extract
Normalize
```

The box then receives a normalized contour dataset.

### Input to the box

``` text
TERRAIN INPUT
────────────────────────────────

1. Contours
   - contour ID
   - contour elevation
   - contour geometry
   - ordered coordinates

2. Coordinate Reference System
   - spatial reference information

3. Analysis Extent
   - bounding region / terrain extent

4. Processing Parameters
   - grid resolution
   - terrain-processing parameters
   - hydrological thresholds
```

The core input can therefore be summarized as:

``` text
Contour Geometry
       +
Contour Elevation
       +
Spatial Reference
       +
Analysis Extent
       +
Processing Parameters
```

------------------------------------------------------------------------

# 2.3 Example of the KML-to-Algorithm Transformation

Raw KML:

``` text
<Placemark>
    <name>277.0</name>
    ...
    <LineString>
        <coordinates>
            81.2863,21.2635
            81.2863,21.2635
            ...
        </coordinates>
    </LineString>
</Placemark>
```

becomes conceptually:

``` text
Contour
    ID: 0
    Elevation: 277 m
    Geometry:
        coordinate 1
        coordinate 2
        coordinate 3
        ...
```

Another:

``` text
Contour
    ID: 1
    Elevation: 280 m
    Geometry:
        coordinate 1
        coordinate 2
        coordinate 3
        ...
```

The algorithm therefore receives:

``` text
Normalized Contour Dataset
```

instead of:

``` text
XML/KML document
```

------------------------------------------------------------------------

# 2.4 What Happens Inside the Box?

The internal processing can be represented as:

``` text
Normalized Contours
        |
        v
Contour Interpolation
        |
        v
DEM / Terrain Grid
        |
        v
Terrain Analysis
        |
        +---- Elevation statistics
        +---- Slope
        +---- Relief
        |
        v
Hydrological Conditioning
        |
        v
Flow Direction
        |
        v
Flow Accumulation
        |
        v
Drainage Network
        |
        v
Depression / Low-point Analysis
        |
        v
Candidate Generation
        |
        v
Catchment Delineation
        |
        v
Terrain / Hydrology Filtering
```

The box therefore hides all of the implementation complexity from the
rest of the backend.

------------------------------------------------------------------------

# 2.5 What Comes Out of the Box?

The output should not simply be:

``` text
Best pond location
```

Instead, the box should produce a complete terrain and hydrology result
that downstream components can use.

The output should contain two broad categories.

------------------------------------------------------------------------

## 2.5.1 Output A --- Terrain and Hydrology Layers

These are the analytical products generated from the terrain:

``` text
DEM / elevation surface
Slope map
Elevation statistics
Flow direction
Flow accumulation
Drainage network
Depression map
```

These layers are useful both for:

-   downstream analysis
-   frontend visualization

------------------------------------------------------------------------

## 2.5.2 Output B --- Pond Candidate Information

The engine should generate multiple candidate locations.

Conceptually:

``` text
Candidate 1
    Location
    Elevation
    Slope
    Flow accumulation
    Depression information
    Catchment area
    Catchment boundary
    Drainage characteristics
    Filtering status
    Reason

Candidate 2
    Location
    Elevation
    Slope
    Flow accumulation
    Depression information
    Catchment area
    Catchment boundary
    Drainage characteristics
    Filtering status
    Reason

...
```

This gives later components enough information to perform rainfall,
runoff, pond sizing, and final ranking.

------------------------------------------------------------------------

# 2.6 Output Structure

The output of the box can therefore be conceptualized as:

``` text
ALGORITHM OUTPUT
────────────────────────────────

Terrain
    - DEM / elevation surface
    - elevation statistics
    - slope
    - terrain characteristics

Hydrology
    - flow direction
    - flow accumulation
    - drainage network

Depressions
    - depression regions
    - local minima
    - spill/outlet information
    - potential ponding regions

Candidates
    - candidate locations
    - candidate regions
    - candidate elevation
    - candidate slope
    - flow accumulation
    - catchment boundary
    - catchment area
    - drainage information

Filtering
    - accepted candidates
    - rejected candidates
    - rejection reasons

Visualization Data
    - geospatial layers suitable for frontend display
```

------------------------------------------------------------------------

# 2.7 River Data Is a Separate Input to Later Suitability Processing

The river visible in the map should not automatically be assumed to be
part of the contour KML.

Therefore, the architecture can be:

``` text
                 Contour KML/KMZ
                        |
                        v
                KML/KMZ Processor
                        |
                        v
             Normalized Contours
                        |
                        v
        ┌──────────────────────────────┐
        │ TERRAIN & HYDROLOGY ENGINE   │
        └──────────────┬───────────────┘
                       |
                       v
           Terrain + Hydrology
             + Candidates
                       |
             ┌─────────┴─────────┐
             |                   |
             v                   v
       Rainfall Data       River / Land /
                           Infrastructure Data
             |                   |
             └─────────┬─────────┘
                       |
                       v
                Suitability /
                Runoff Analysis
                       |
                       v
                Pond Recommendation
```

This prevents the terrain engine from becoming responsible for every
external map layer.

------------------------------------------------------------------------

# 2.8 Hard Filter and Scoring Architecture

The algorithm box can generate candidates and perform
terrain/hydrological filtering.

Later suitability components can apply external constraints.

Conceptually:

``` text
             All Candidates
                    |
                    v
          Terrain/Hydrology Filter
                    |
          +---------+---------+
          |                   |
       Rejected             Valid
                              |
                              v
                    External Constraints
                              |
                    +---------+---------+
                    |                   |
                  Reject             Valid
                                        |
                                        v
                                  Scoring Model
                                        |
                                        v
                               Ranked Candidates
```

This separation makes the backend easier to maintain and explain.

------------------------------------------------------------------------

# 2.9 Interface Between the Box and the Next Components

The algorithm box should produce a standardized result.

The next component should not need to know:

-   how the DEM was interpolated
-   how D8 was calculated
-   how depressions were detected
-   how graph traversal was implemented

It only needs the results.

For example:

``` text
Candidate
    |
    +-- location
    +-- elevation
    +-- slope
    +-- catchment area
    +-- catchment boundary
    +-- flow accumulation
    +-- drainage information
    +-- depression information
```

The next component can then combine this with:

``` text
Rainfall
+
Catchment
+
Runoff assumptions
```

to estimate runoff.

------------------------------------------------------------------------

# 2.10 Why This Box Boundary Is Useful

The architecture now has a clean separation:

### KML Processor

Responsible for:

``` text
Raw file
    ↓
Parsed and normalized contours
```

### Terrain & Hydrology Engine

Responsible for:

``` text
Contours
    ↓
Terrain
    ↓
Water movement
    ↓
Catchments
    ↓
Pond candidates
```

### Rainfall Component

Responsible for:

``` text
Rainfall provider
    ↓
Normalized rainfall data
```

### Runoff Component

Responsible for:

``` text
Rainfall
+
Catchment
+
Runoff assumptions
    ↓
Estimated runoff
```

### Pond Sizing Component

Responsible for:

``` text
Runoff
+
Terrain/candidate information
    ↓
Depth
Surface area
Storage capacity
Approximate dimensions
```

### Candidate Scoring / Recommendation

Responsible for:

``` text
Candidate information
+
Rainfall
+
Runoff
+
Constraints
    ↓
Ranked candidates
    ↓
Best recommendation
```

This follows the intended modular design where terrain, rainfall,
runoff, and pond sizing are independently testable and the final API
acts as an orchestrator rather than containing every algorithm itself.

------------------------------------------------------------------------

# 2.11 Complete Backend View With the Box

The current backend can therefore be visualized as:

``` text
                         USER
                          |
                          v
                    KML / KMZ Upload
                          |
                          v
                ┌────────────────────┐
                │  KML/KMZ Processor │
                │                    │
                │ Validate            │
                │ Parse               │
                │ Extract             │
                │ Normalize           │
                └─────────┬──────────┘
                          |
                          v
                 Normalized Contours
                          |
                          v
        ╔══════════════════════════════════════╗
        ║      TERRAIN & HYDROLOGY BOX        ║
        ║                                      ║
        ║  Contours                            ║
        ║      ↓                               ║
        ║  DEM / Elevation Grid                ║
        ║      ↓                               ║
        ║  Terrain Analysis                    ║
        ║      ↓                               ║
        ║  Flow Direction                      ║
        ║      ↓                               ║
        ║  Flow Accumulation                   ║
        ║      ↓                               ║
        ║  Drainage Network                   ║
        ║      ↓                               ║
        ║  Depression Analysis                ║
        ║      ↓                               ║
        ║  Candidate Generation               ║
        ║      ↓                               ║
        ║  Catchment Delineation              ║
        ║      ↓                               ║
        ║  Terrain/Hydrology Filtering        ║
        ╚══════════════════╤═══════════════════╝
                           |
                           v
              Terrain + Hydrology Results
                           |
             +-------------+-------------+
             |                           |
             v                           v
       Rainfall Component        External Constraints
             |                    (river/land/etc.)
             |                           |
             +-------------+-------------+
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
                  Ranked Recommendations
                           |
                           v
                 Structured JSON
                 + GeoJSON Layers
```

------------------------------------------------------------------------

# 2.12 Final Definition of the Algorithm Box

For the current Phase 2 backend, the **Terrain & Hydrology Engine** can
be defined as:

> **A processing component that accepts normalized contour geometry and
> elevation data, reconstructs a terrain surface, models downhill water
> movement, identifies drainage and depressions, generates potential
> pond locations, delineates their contributing catchments, and returns
> terrain/hydrological layers and candidate information for downstream
> rainfall, runoff, suitability, and pond-sizing components.**

Its fundamental transformation is:

``` text
Contour Information
        ↓
Terrain Representation
        ↓
Water Movement Representation
        ↓
Catchment / Depression Information
        ↓
Potential Pond Candidates
```

The central algorithmic principle is:

``` text
Do NOT:
    Lowest point = pond

Instead:
    Generate candidates
        ↓
    Analyze terrain
        ↓
    Analyze water flow
        ↓
    Analyze catchment
        ↓
    Check constraints
        ↓
    Score candidates
        ↓
    Recommend
```

This makes the component explainable, modular, testable, and suitable
for integration with the later rainfall, runoff, pond-sizing, and
recommendation stages.

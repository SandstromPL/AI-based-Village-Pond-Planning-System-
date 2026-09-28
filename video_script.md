# Demo Video Script — AI-based Village Pond Planning System

> Target: 5:00 total, hard cap per the assignment brief. Timestamps are
> budgets, not exact cues — practice once and trim wherever you run long
> (the Discussion beat at 4:15–4:35 is the safest place to cut if needed).
> Record your screen at 1080p+, and do a dry run of the live-draw demo
> beforehand once against your deployed backend so you know roughly how
> long the real API calls take that day — narrate over the wait rather
> than sitting in silence (see the note at 2:40).

---

## 0:00–0:20 — Hook + problem statement

**[SCREEN: title slide or the app's landing view, sidebar visible]**

> "Choosing where to build a small pond or check-dam in a village today is
> done by manual site inspection — no terrain analysis, no catchment
> estimate, no rainfall data. This project automates that decision: given
> either a contour map or an area drawn on a map, it recommends a pond
> location, computes its catchment area, and estimates how much water it
> can collect — all in seconds."

---

## 0:20–0:55 — Architecture, tech stack (fast overview)

**[SCREEN: architecture diagram, or just narrate over the app]**

> "It's a three-tier system. A React and Leaflet frontend talks to a
> FastAPI backend over a REST API. The backend is layered — API routes,
> orchestration services, pure algorithms, and external-provider
> integrations — each layer independently testable. Six external data
> sources feed it: for terrain, when there's no contour file, elevation is
> read directly from Copernicus DEM — real satellite elevation data hosted
> as public cloud storage — falling back through three more elevation
> APIs if that's ever unavailable; Open-Meteo supplies historical
> rainfall; and the Overpass API pulls real OpenStreetMap data on
> buildings, roads, and rivers. There's no database — results are computed
> fresh from live data on every request."

---

## 0:55–2:35 — The algorithm (the core of the report's methodology section)

This is the section the assignment explicitly wants explained in detail.
Speak a little slower here; consider a simple on-screen diagram or just
zoom into the map layers as you name each stage.

**[SCREEN: a completed analysis result, zoomed on the map]**

> "Here's the pipeline, in order.

> First, terrain. From an uploaded contour map, contour lines are parsed
> and interpolated onto a grid — a Digital Elevation Model. From a
> drawn area, that same grid is built by reading real elevation values
> directly from Copernicus DEM, a satellite-derived global elevation
> dataset — no rate limits, since it's read as a plain cloud-hosted file
> rather than queried through an API — with three more elevation
> providers as fallback if that's ever unreachable.

> Second, hydrological conditioning. Raw elevation data has small
> artificial pits that would trap water unrealistically — Priority-Flood
> depression filling raises those pits to their spill point, guaranteeing
> continuous downhill drainage.

> Third, flow analysis. For every grid cell, D8 flow direction picks the
> steepest downhill neighbor among eight. Flow accumulation then counts,
> for every cell, how many upstream cells drain into it — this is what
> tells us where water actually converges.

> Fourth, candidates. The system looks for two signals: natural
> depressions, and high flow-accumulation points — places water is
> already converging. These get merged, de-duplicated, and then filtered:
> too steep, rejected. Catchment too small, rejected. And — this one uses
> live OpenStreetMap data — if the point falls on or near an existing
> building, road, or river, it's rejected too."

**[SCREEN: point at a rejected red marker near a road on the map]**

> "You can see that here — this rejected candidate sits right on a real
> road.

> Fifth, for every surviving candidate, its full catchment — the entire
> upstream area that drains to it — is delineated and scored on five
> factors: catchment size, flow accumulation, slope, relief, and
> depression depth.

> Finally, real historical rainfall for that exact location feeds a
> Rational Method runoff calculation — rainfall times catchment area
> times a runoff coefficient — which sizes the recommended pond: depth,
> surface area, and total storage volume."

---

## 2:35–4:15 — Live demo

**[SCREEN: switch to the live app]**

> "Let's see it live."

**Option A — contour upload path** (use if you have a KML ready and want
the fast, reliable path):
- Upload the sample KML, click Analyze.
- While it processes (should be a few seconds): *"This is reconstructing
  the terrain from the contour lines, running the full pipeline I just
  described, and querying live rainfall data — no mocked data anywhere."*
- Once results appear, walk the map: point at the gold recommended marker,
  a green accepted candidate, a red rejected one, and a catchment boundary
  polygon. Open the results panel and read out: recommended catchment
  area, expected annual water collection, and planned pond storage.

**Option B — draw-on-map path** (use this one if you want to also show
the assignment's specific "select an area on the map" requirement):
- Switch to "Draw Area on Map", draw a rectangle over a real area.
- Click Analyze. **[This calls up to six live external data sources over the real
  network — it can take anywhere from a few seconds to over a minute
  depending on how those services are behaving right now. Narrate over
  the wait: don't just stare at a loading spinner on camera.]**
- While waiting: *"This is fetching real elevation data for every grid
  cell from a live API right now — no synthetic data. If any of these
  external services is slow or unavailable, the system is built to
  degrade gracefully rather than fail outright — it'll still return a
  result, just with a warning telling you which part was affected."*
- If a warning banner about rainfall or land-use actually appears when you
  record this — don't panic and don't re-record. Point at it and say
  exactly that: *"You can see one of those warnings right here — this is
  the resilience design working as intended, not a bug."* This is a
  genuinely good demo moment, not something to hide.
- Walk the resulting map the same way as Option A.

**[SCREEN: quickly show the theme switch and sidebar resize]**

> "Dark and light themes, and the results panel is resizable if you want
> more room for the map."

*(If time is tight, cut this beat entirely — it's the least essential 10
seconds in the script.)*

---

## 4:15–4:45 — Resilience, briefly (ties back to "stress, scaling, system limitations")

**[SCREEN: can stay on the results, or cut to a terminal/log view if you have one]**

> "Because this depends on six free external data sources, and none of
> them guarantee uptime, every one of them is wrapped so a failure
> degrades to an explicit 'unavailable' status instead of crashing the
> request. During development, every single one of them failed for real
> at least once — DNS failures, confirmed rate limits, connection resets —
> and the system kept working through all of it, including a circuit
> breaker that stops retrying a provider that's currently down instead of
> repeating the same failure on every request."

---

## 4:45–5:00 — Close

**[SCREEN: back to the landing view or a results overview]**

> "That's the AI-based Village Pond Planning System — terrain and
> hydrology analysis, real rainfall data, and a land-use safety check,
> all exposed through a simple map interface. Thanks for watching."

---

## Recording checklist

- [ ] Confirm the deployed frontend is pointed at a **currently reachable**
      backend right before recording (health-check it) — a dead backend
      mid-recording is the single most likely thing to force a re-take.
- [ ] Have a KML file ready in the file picker's recent list or a known
      folder, so the upload demo doesn't stall searching for it on camera.
- [ ] Decide upload-only vs. upload+draw *before* recording, based on how
      much of the 5:00 budget the algorithm explanation actually took in
      your dry run — don't try to fit both if the first half already ran
      long.
- [ ] Upload to YouTube as **Public** or **Unlisted** (Unlisted still
      satisfies "a public link" as long as anyone with the link can view
      it — confirm this is acceptable per your course's exact wording
      before relying on it; Public is the safer default if unsure).
- [ ] Paste the final link into `report.tex`'s Appendix
      (`\S`Source Code and Repository`, currently a placeholder) before
      submitting the report.

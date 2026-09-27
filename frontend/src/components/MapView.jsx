import { useEffect, useMemo, useRef } from 'react'
import { GeoJSON, LayersControl, MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet-draw'
import { filterValidFeatures, hasFeatures, isValidFeature } from '../utils/geojson.js'
import { prettify, safe, safeNumber } from '../utils/format.js'

// IIT Bhilai campus — matches the backend's sample contour dataset, a
// sensible default center rather than an arbitrary point on the globe.
const DEFAULT_CENTER = [21.2632, 81.2828]
const DEFAULT_ZOOM = 15

// Esri's public "Canvas"/"World_Imagery" REST tile services — free, no API
// key, no signup. (CARTO's basemaps.cartocdn.com free tier was retired and
// now serves an "API KEY REQUIRED" watermark instead of real tiles —
// confirmed by actually loading the app and looking at a screenshot.)
// Esri's "Canvas" Dark/Light Gray basemaps look good but have real gaps in
// rural coverage (confirmed live: a rural India location at zoom 17 served
// an actual "Map data not yet available" placeholder tile, not just a
// styling issue). Standard OpenStreetMap tiles have complete global
// coverage, so both themes use the same real OSM tiles — dark is a CSS
// filter (see .map-tiles--dark in index.css), not a different tile source.
const TILE_LAYERS = {
  osm: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics',
  },
}

function FitBounds({ bbox }) {
  const map = useMap()

  useEffect(() => {
    if (!bbox) return
    const { min_lat, min_lon, max_lat, max_lon } = bbox
    if ([min_lat, min_lon, max_lat, max_lon].some((v) => typeof v !== 'number')) return
    try {
      map.fitBounds(
        [
          [min_lat, min_lon],
          [max_lat, max_lon],
        ],
        { padding: [40, 40], maxZoom: 17 },
      )
    } catch {
      // A malformed bbox should never take down the map — just skip fitting.
    }
  }, [bbox, map])

  return null
}

// Wraps leaflet-draw imperatively — react-leaflet has no draw control of
// its own. Callbacks are read from refs so the draw control (and its
// event listeners) is only ever created/destroyed once per mount, not on
// every render when the parent passes new callback identities.
function DrawTools({ onDrawn, onCleared, clearSignal }) {
  const map = useMap()
  const featureGroupRef = useRef(null)
  const onDrawnRef = useRef(onDrawn)
  const onClearedRef = useRef(onCleared)

  useEffect(() => {
    onDrawnRef.current = onDrawn
  }, [onDrawn])

  useEffect(() => {
    onClearedRef.current = onCleared
  }, [onCleared])

  useEffect(() => {
    const featureGroup = new L.FeatureGroup()
    featureGroupRef.current = featureGroup
    map.addLayer(featureGroup)

    const drawControl = new L.Control.Draw({
      draw: {
        rectangle: true,
        polygon: { allowIntersection: false, showArea: true },
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      },
      edit: { featureGroup, remove: true },
    })
    map.addControl(drawControl)

    function extractRing(layer) {
      const rings = layer.getLatLngs()
      return Array.isArray(rings[0]) ? rings[0] : rings
    }

    function handleCreated(event) {
      // One shape at a time keeps the mental model simple for the user.
      featureGroup.clearLayers()
      featureGroup.addLayer(event.layer)
      onDrawnRef.current(extractRing(event.layer))
    }

    function handleEdited(event) {
      event.layers.eachLayer((layer) => onDrawnRef.current(extractRing(layer)))
    }

    function handleDeleted() {
      if (featureGroup.getLayers().length === 0) onClearedRef.current()
    }

    map.on(L.Draw.Event.CREATED, handleCreated)
    map.on(L.Draw.Event.EDITED, handleEdited)
    map.on(L.Draw.Event.DELETED, handleDeleted)

    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated)
      map.off(L.Draw.Event.EDITED, handleEdited)
      map.off(L.Draw.Event.DELETED, handleDeleted)
      map.removeControl(drawControl)
      map.removeLayer(featureGroup)
    }
  }, [map])

  useEffect(() => {
    if (clearSignal) featureGroupRef.current?.clearLayers()
  }, [clearSignal])

  return null
}

export default function MapView({ theme, result, mode, onAreaDrawn, onAreaCleared, clearSignal }) {
  const layers = useMemo(() => {
    const gj = result?.geojson_layers
    if (!gj) return null
    return {
      contours: filterValidFeatures(gj.contour_lines),
      candidates: filterValidFeatures(gj.candidates),
      catchments: filterValidFeatures(gj.catchment_boundaries),
      recommended: isValidFeature(gj.recommended_location) ? gj.recommended_location : null,
    }
  }, [result])

  const analysisKey = result?.analysis_id ?? 'no-result'

  return (
    <div className="map-view">
      <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} scrollWheelZoom>
        {/* Keyed on theme: react-leaflet's BaseLayer `checked` prop only
            applies at mount, so remounting the whole control is what makes
            the theme switch actually change the visible base map instead
            of only the UI chrome around it. */}
        <LayersControl position="topright" key={theme}>
          <LayersControl.BaseLayer name="Dark" checked={theme === 'dark'}>
            <TileLayer
              url={TILE_LAYERS.osm.url}
              attribution={TILE_LAYERS.osm.attribution}
              className="map-tiles--dark"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Light" checked={theme === 'light'}>
            <TileLayer url={TILE_LAYERS.osm.url} attribution={TILE_LAYERS.osm.attribution} />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite">
            <TileLayer
              url={TILE_LAYERS.satellite.url}
              attribution={TILE_LAYERS.satellite.attribution}
            />
          </LayersControl.BaseLayer>

          {hasFeatures(layers?.contours) && (
            <LayersControl.Overlay checked name="Contour Lines">
              <GeoJSON
                key={`${analysisKey}-contours`}
                data={layers.contours}
                style={() => ({ color: '#8a8fa3', weight: 1, opacity: 0.7 })}
              />
            </LayersControl.Overlay>
          )}

          {hasFeatures(layers?.catchments) && (
            <LayersControl.Overlay checked name="Catchment Boundaries">
              <GeoJSON
                key={`${analysisKey}-catchments`}
                data={layers.catchments}
                style={(feature) => ({
                  color: feature?.properties?.is_recommended ? '#22c55e' : '#38bdf8',
                  weight: 2,
                  fillOpacity: 0.15,
                })}
                onEachFeature={(feature, layer) => {
                  const p = feature.properties || {}
                  layer.bindPopup(
                    `Catchment area: ${safeNumber(p.area_km2, 4)} km²<br/>Rank: ${safe(p.rank)}`,
                  )
                }}
              />
            </LayersControl.Overlay>
          )}

          {hasFeatures(layers?.candidates) && (
            <LayersControl.Overlay checked name="Candidates">
              <GeoJSON
                key={`${analysisKey}-candidates`}
                data={layers.candidates}
                pointToLayer={(feature, latlng) =>
                  L.circleMarker(latlng, {
                    radius: feature.properties?.rank === 1 ? 8 : 5,
                    color: feature.properties?.status === 'accepted' ? '#22c55e' : '#f87171',
                    fillOpacity: 0.8,
                    weight: 1,
                  })
                }
                onEachFeature={(feature, layer) => {
                  const p = feature.properties || {}
                  const lines = [
                    `<strong>${safe(p.id)}</strong> — ${prettify(p.status)}`,
                    `Score: ${safeNumber(p.score, 1)}`,
                    `Catchment: ${safeNumber(p.catchment_area_km2, 4)} km²`,
                  ]
                  if (p.rejection_reason) lines.push(`Reason: ${prettify(p.rejection_reason)}`)
                  if (p.expected_annual_collection_m3 != null) {
                    lines.push(`Expected volume: ${safeNumber(p.expected_annual_collection_m3, 0)} m³`)
                  }
                  layer.bindPopup(lines.join('<br/>'))
                }}
              />
            </LayersControl.Overlay>
          )}
        </LayersControl>

        {layers?.recommended && (
          <GeoJSON
            key={`${analysisKey}-recommended`}
            data={layers.recommended}
            pointToLayer={(feature, latlng) =>
              L.circleMarker(latlng, {
                radius: 10,
                color: '#facc15',
                fillColor: '#facc15',
                fillOpacity: 0.9,
                weight: 2,
              })
            }
            onEachFeature={(feature, layer) => {
              const p = feature.properties || {}
              layer.bindPopup(
                [
                  '<strong>Recommended Pond</strong>',
                  `Catchment: ${safeNumber(p.catchment_area_km2, 4)} km²`,
                  `Expected volume: ${safeNumber(p.expected_annual_collection_m3, 0)} m³`,
                  `Planned storage: ${safeNumber(p.planned_storage_m3, 0)} m³`,
                ].join('<br/>'),
              )
            }}
          />
        )}

        <FitBounds bbox={result?.input?.bbox} />

        {mode === 'draw' && (
          <DrawTools onDrawn={onAreaDrawn} onCleared={onAreaCleared} clearSignal={clearSignal} />
        )}
      </MapContainer>
    </div>
  )
}

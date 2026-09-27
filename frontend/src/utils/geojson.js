// Defensive GeoJSON helpers. The backend is correct today (it emits
// geometry: null instead of an empty coordinates array when there's no
// recommended candidate — see RFC 7946 §3.2), but the frontend must not
// assume every future producer of these layers will always get that right,
// especially once a building/road/river exclusion layer is added upstream.

export function filterValidFeatures(featureCollection) {
  if (!featureCollection || !Array.isArray(featureCollection.features)) {
    return { type: 'FeatureCollection', features: [] }
  }
  return {
    type: 'FeatureCollection',
    features: featureCollection.features.filter(isValidFeature),
  }
}

export function isValidFeature(feature) {
  return Boolean(
    feature &&
      feature.geometry &&
      feature.geometry.type &&
      Array.isArray(feature.geometry.coordinates) &&
      feature.geometry.coordinates.length > 0,
  )
}

export function hasFeatures(featureCollection) {
  return (
    Boolean(featureCollection) &&
    Array.isArray(featureCollection.features) &&
    featureCollection.features.length > 0
  )
}

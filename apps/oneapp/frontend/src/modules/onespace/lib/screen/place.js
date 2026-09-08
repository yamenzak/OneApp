/**
 * Where a record is, out of whichever field it keeps that in.
 *
 * Two shapes, because the field a doctype already has decides which. Frappe's
 * `Geolocation` holds GeoJSON — a FeatureCollection, usually with one Point,
 * sometimes with a line or a polygon somebody drew. And a pair of numeric
 * fields, which is what every address table in the world actually has;
 * ERPNext's own Address carries `latitude` and `longitude` as Floats.
 *
 * Everything reduces to one point per record, because a pin is what a list of
 * records on a map *is*. A shape's point is its first coordinate rather than a
 * true centroid: a centroid of a concave polygon can land outside it, which
 * puts the pin in the sea, and the first vertex is at least somewhere the
 * shape passes through.
 *
 * Pure, so `place.test.js` can hold it to the eight shapes of input a real
 * feed produces without a browser or a map.
 */

/** Longitude and latitude are in that order in GeoJSON, and nowhere else. */
function pair(lon, lat) {
  const x = Number(lon)
  const y = Number(lat)
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  // Off the earth is not a position. Zero is a real place — Null Island is in
  // the Atlantic — but a row where *both* are exactly zero is an unset field
  // in every dataset anybody has, so it is treated as absent.
  if (x < -180 || x > 180 || y < -90 || y > 90) return null
  if (x === 0 && y === 0) return null
  return [x, y]
}

function firstCoordinate(geometry) {
  if (!geometry) return null
  const { type, coordinates } = geometry
  if (!Array.isArray(coordinates)) return null
  if (type === 'Point') return pair(coordinates[0], coordinates[1])

  // Everything else nests: LineString is an array of points, Polygon an array
  // of rings, MultiPolygon an array of those. Walk down to the first pair.
  let at = coordinates
  while (Array.isArray(at) && Array.isArray(at[0])) at = at[0]
  return pair(at?.[0], at?.[1])
}

/** One record's position, or null. Exported for the live map's own reuse. */
export function pointOf(row, place) {
  if (!row || !place) return null

  const field = place.point_field
  if (field) {
    const raw = row[field]
    if (!raw) return null
    let parsed = raw
    if (typeof raw === 'string') {
      try {
        parsed = JSON.parse(raw)
      } catch {
        return null
      }
    }
    if (parsed?.type === 'FeatureCollection') {
      for (const feature of parsed.features || []) {
        const found = firstCoordinate(feature?.geometry)
        if (found) return found
      }
      return null
    }
    if (parsed?.type === 'Feature') return firstCoordinate(parsed.geometry)
    return firstCoordinate(parsed)
  }

  if (place.lat_field && place.lon_field) {
    return pair(row[place.lon_field], row[place.lat_field])
  }
  return null
}

/**
 * The page as GeoJSON, ready to hand a map.
 *
 * `label` and `theme` are functions rather than field names because the caller
 * already knows how to read a value the way the rest of the product reads it —
 * a Select's declared colour, a title field's fallback — and duplicating that
 * here would be a second answer to a question with one.
 */
export function featuresFrom(rows, place, { label, theme, ink } = {}) {
  const out = []
  for (const row of rows || []) {
    const at = pointOf(row, place)
    if (!at) continue
    out.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: at },
      properties: {
        name: row.name,
        label: label ? label(row) : String(row.name ?? ''),
        ink: ink ? ink(theme ? theme(row) : 'gray') : '#8b8b8b',
      },
    })
  }
  return out
}

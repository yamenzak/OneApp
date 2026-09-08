import { describe, expect, it } from 'vitest'

import { featuresFrom, pointOf } from './place'

const GEO = { point_field: 'where' }
const PAIR = { lat_field: 'lat', lon_field: 'lon' }

function collection(geometry) {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: [{ type: 'Feature', properties: {}, geometry }],
  })
}

describe('pointOf', () => {
  it('reads a Point out of a Geolocation collection', () => {
    const row = { where: collection({ type: 'Point', coordinates: [13.4, 52.5] }) }
    expect(pointOf(row, GEO)).toEqual([13.4, 52.5])
  })

  it('takes the first vertex of a line rather than a centroid', () => {
    // A centroid of a concave shape can land outside it, which puts the pin in
    // the sea. The first vertex is at least somewhere the shape passes.
    const row = {
      where: collection({ type: 'LineString', coordinates: [[1, 2], [3, 4], [5, 6]] }),
    }
    expect(pointOf(row, GEO)).toEqual([1, 2])
  })

  it('walks down a polygon and a multipolygon', () => {
    const ring = [[[10, 20], [11, 21], [12, 22], [10, 20]]]
    expect(pointOf({ where: collection({ type: 'Polygon', coordinates: ring }) }, GEO))
      .toEqual([10, 20])
    expect(
      pointOf({ where: collection({ type: 'MultiPolygon', coordinates: [ring] }) }, GEO)
    ).toEqual([10, 20])
  })

  it('accepts an already-parsed object as well as a string', () => {
    const row = { where: { type: 'Point', coordinates: [1, 1] } }
    expect(pointOf(row, GEO)).toEqual([1, 1])
  })

  it('is not fooled by an empty field, bad JSON, or an empty collection', () => {
    expect(pointOf({ where: '' }, GEO)).toBe(null)
    expect(pointOf({ where: '{not json' }, GEO)).toBe(null)
    expect(pointOf({ where: '{"type":"FeatureCollection","features":[]}' }, GEO)).toBe(null)
  })

  it('reads a numeric pair, longitude second in the row and first in GeoJSON', () => {
    expect(pointOf({ lat: 52.5, lon: 13.4 }, PAIR)).toEqual([13.4, 52.5])
    expect(pointOf({ lat: '52.5', lon: '13.4' }, PAIR)).toEqual([13.4, 52.5])
  })

  it('refuses a position off the earth', () => {
    expect(pointOf({ lat: 91, lon: 0 }, PAIR)).toBe(null)
    expect(pointOf({ lat: 0, lon: 181 }, PAIR)).toBe(null)
  })

  it('treats an exact 0,0 as an unset field rather than as Null Island', () => {
    expect(pointOf({ lat: 0, lon: 0 }, PAIR)).toBe(null)
    // But a real zero on one axis is a real place.
    expect(pointOf({ lat: 51.48, lon: 0 }, PAIR)).toEqual([0, 51.48])
  })

  it('says nothing when the screen declares nothing', () => {
    expect(pointOf({ lat: 1, lon: 1 }, {})).toBe(null)
    expect(pointOf(null, PAIR)).toBe(null)
  })
})

describe('featuresFrom', () => {
  const rows = [
    { name: 'a', lat: 52.5, lon: 13.4, kind: 'Open' },
    { name: 'b', lat: null, lon: null },
    { name: 'c', lat: 48.1, lon: 11.6, kind: 'Closed' },
  ]

  it('drops the records with nowhere to be, and keeps the rest in order', () => {
    const out = featuresFrom(rows, PAIR)
    expect(out.map((f) => f.properties.name)).toEqual(['a', 'c'])
    expect(out[0].geometry).toEqual({ type: 'Point', coordinates: [13.4, 52.5] })
  })

  it('asks the caller for the label and the colour rather than deciding', () => {
    const out = featuresFrom(rows, PAIR, {
      label: (row) => row.kind,
      theme: (row) => (row.kind === 'Open' ? 'green' : 'red'),
      ink: (theme) => (theme === 'green' ? '#0a0' : '#a00'),
    })
    expect(out.map((f) => f.properties.label)).toEqual(['Open', 'Closed'])
    expect(out.map((f) => f.properties.ink)).toEqual(['#0a0', '#a00'])
  })

  it('survives no rows at all', () => {
    expect(featuresFrom(null, PAIR)).toEqual([])
    expect(featuresFrom([], PAIR)).toEqual([])
  })
})

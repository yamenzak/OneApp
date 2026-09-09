import { describe, expect, it } from 'vitest'

import { at, between, blend, ease, measure, prepare, project, tangent } from './motion'

// A right angle: east one degree, then north one degree. A straight line
// between the two ends would cut the corner, which is the whole point.
const CORNER = [[0, 0], [1, 0], [1, 1]]

describe('measure', () => {
  it('is cumulative and starts at zero', () => {
    expect(measure(CORNER)).toEqual([0, 1, 2])
  })
})

describe('project', () => {
  const along = measure(CORNER)

  it('puts a point beside the line onto the line', () => {
    // Half a degree east and a little north of the road.
    expect(project(CORNER, along, 0.5, 0.2)).toBeCloseTo(0.5, 6)
  })

  it('clamps past either end rather than running off', () => {
    expect(project(CORNER, along, -5, 0)).toBeCloseTo(0, 6)
    expect(project(CORNER, along, 1, 9)).toBeCloseTo(2, 6)
  })

  it('survives a doubled vertex, which real feeds are full of', () => {
    const doubled = [[0, 0], [0, 0], [1, 0]]
    expect(project(doubled, measure(doubled), 0.5, 0)).toBeCloseTo(0.5, 6)
  })

  it('says zero for a shape too short to project onto', () => {
    expect(project([[0, 0]], [0], 1, 1)).toBe(0)
  })
})

describe('at', () => {
  const along = measure(CORNER)

  it('finds a point in the first span and in the second', () => {
    expect(at(CORNER, along, 0.25)).toEqual([0.25, 0])
    expect(at(CORNER, along, 1.5)).toEqual([1, 0.5])
  })

  it('clamps to the ends', () => {
    expect(at(CORNER, along, -1)).toEqual([0, 0])
    expect(at(CORNER, along, 99)).toEqual([1, 1])
  })

  it('returns the single vertex of a degenerate shape', () => {
    expect(at([[3, 4]], [0], 10)).toEqual([3, 4])
  })
})

describe('between', () => {
  const shape = prepare({ type: 'LineString', coordinates: CORNER })
  const previous = { lon: 0, lat: 0 }
  const latest = { lon: 1, lat: 1 }

  it('follows the corner rather than cutting it', () => {
    const half = between(shape, previous, latest, 0.5)
    // Half of two degrees along the shape is the corner itself — not [0.5, 0.5],
    // which is where a straight line would have put it, in the field.
    expect(half[0]).toBeCloseTo(1, 6)
    expect(half[1]).toBeCloseTo(0, 6)
  })

  it('extrapolates a little past the last report, and no further', () => {
    const far = between(shape, previous, latest, 99)
    expect(far).toEqual([1, 1])
  })

  it('falls back to the reported position with no usable shape', () => {
    expect(between(null, previous, latest, 0.5)).toEqual([1, 1])
    expect(between(prepare({ coordinates: [[0, 0]] }), previous, latest, 0.5))
      .toEqual([1, 1])
  })

  it('has nothing to say without a latest report', () => {
    expect(between(shape, previous, null, 0.5)).toBe(null)
  })
})

describe('ease and blend', () => {
  it('eases out, and is clamped at both ends', () => {
    expect(ease(0)).toBe(0)
    expect(ease(1)).toBe(1)
    expect(ease(-3)).toBe(0)
    expect(ease(0.5)).toBeGreaterThan(0.5)
  })

  it('walks one position onto another', () => {
    expect(blend([0, 0], [10, 0], 0)).toEqual([0, 0])
    expect(blend([0, 0], [10, 0], 1)).toEqual([10, 0])
    expect(blend(null, [1, 2], 0.5)).toEqual([1, 2])
  })
})

describe('prepare', () => {
  it('refuses a shape that cannot be followed', () => {
    expect(prepare(null)).toBe(null)
    expect(prepare({ coordinates: [] })).toBe(null)
    expect(prepare({ coordinates: [[1, 1]] })).toBe(null)
  })
})

describe('tangent', () => {
  // A shape running due east, then due north.
  const points = [[0, 0], [1, 0], [1, 1]]
  const along = measure(points)

  it('reads the direction of the leg it is on', () => {
    expect(tangent(points, along, 0.5)).toBeCloseTo(90, 0)
    expect(tangent(points, along, 1.5)).toBeCloseTo(0, 0)
  })

  it('turns a vehicle running the route the other way', () => {
    expect(tangent(points, along, 0.5, true)).toBeCloseTo(270, 0)
    expect(tangent(points, along, 1.5, true)).toBeCloseTo(180, 0)
  })

  it('clamps to the ends rather than reading past them', () => {
    expect(tangent(points, along, -9)).toBeCloseTo(90, 0)
    expect(tangent(points, along, 99)).toBeCloseTo(0, 0)
  })

  it('has no direction to give for a shape that is not one', () => {
    expect(tangent([[1, 1]], [0], 0)).toBe(0)
    expect(tangent(null, [], 0)).toBe(0)
  })
})

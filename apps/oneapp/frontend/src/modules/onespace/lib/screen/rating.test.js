import { describe, expect, it } from 'vitest'
import { STARS, ratingOf, starsOf } from '@/modules/onespace/lib/screen/rating'

/*
 * Frappe stores a Rating as a fraction of one and frappe-ui's Rating counts
 * whole stars. The two were handed to each other unconverted, which was wrong
 * in both directions: a four-star candidate drew one star, and clicking the
 * fourth star stored a rating of four hundred per cent.
 */
describe('starsOf', () => {
  it('turns the stored fraction into whole stars', () => {
    expect(starsOf(0.8)).toBe(4)
    expect(starsOf(0.6)).toBe(3)
    expect(starsOf(1)).toBe(STARS)
    expect(starsOf(0)).toBe(0)
  })

  it('reads nothing as no stars rather than as NaN', () => {
    expect(starsOf(null)).toBe(0)
    expect(starsOf(undefined)).toBe(0)
    expect(starsOf('')).toBe(0)
    expect(starsOf('not a number')).toBe(0)
  })

  it('clamps, because the column has held a four before now', () => {
    expect(starsOf(4)).toBe(STARS)
    expect(starsOf(-1)).toBe(0)
  })
})

describe('ratingOf', () => {
  it('turns whole stars back into the fraction to store', () => {
    expect(ratingOf(4)).toBe(0.8)
    expect(ratingOf(5)).toBe(1)
    expect(ratingOf(0)).toBe(0)
  })

  it('clamps a click that could not have happened', () => {
    expect(ratingOf(9)).toBe(1)
    expect(ratingOf(-2)).toBe(0)
  })

  it('round-trips every whole star', () => {
    for (let star = 0; star <= STARS; star += 1) {
      expect(starsOf(ratingOf(star))).toBe(star)
    }
  })
})

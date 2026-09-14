import { describe, expect, it } from 'vitest'

import { DEFAULT_PERIOD, PERIODS, spanOf, stamp } from './periods'

// A Wednesday in the middle of a quarter, west of Greenwich by nothing — the
// point of passing `now` in is that none of this depends on when it runs.
const NOW = new Date(2026, 8, 14) // 14 September 2026

describe('stamp', () => {
  it('is the reader own day, not the UTC one', () => {
    // The whole reason this is not `toISOString().slice(0, 10)`: the first of
    // a month at midnight is the last of the month before in UTC, anywhere
    // west of Greenwich, and a period control that quietly drops a day is
    // worse than no period control.
    expect(stamp(new Date(2026, 0, 1))).toBe('2026-01-01')
    expect(stamp(new Date(2026, 11, 31))).toBe('2026-12-31')
  })
})

describe('spanOf', () => {
  it('runs a month from its first day to its last', () => {
    expect(spanOf('month', NOW)).toEqual(['2026-09-01', '2026-09-30'])
  })

  it('puts a quarter on the quarter boundaries, not on today', () => {
    expect(spanOf('quarter', NOW)).toEqual(['2026-07-01', '2026-09-30'])
  })

  it('ends a year in December rather than today', () => {
    // `to_date` is the end of the span, so a leave application booked for
    // December is still counted in "this year" — a dashboard clipped at today
    // answers a different question from the calendar beside it.
    expect(spanOf('year', NOW)).toEqual(['2026-01-01', '2026-12-31'])
  })

  it('rolls twelve months back to the day after, so the span is twelve', () => {
    expect(spanOf('rolling', NOW)).toEqual(['2025-09-15', '2026-09-14'])
  })

  it('is nothing at all for all of time, and for anything it does not know', () => {
    expect(spanOf('all', NOW)).toBe(null)
    expect(spanOf('', NOW)).toBe(null)
    expect(spanOf('fortnight', NOW)).toBe(null)
  })
})

describe('the list', () => {
  it('offers the default', () => {
    expect(PERIODS.map((one) => one.value)).toContain(DEFAULT_PERIOD)
  })

  it('defaults to the one that narrows nothing', () => {
    // A dashboard that opened already narrowed would disagree with the list
    // beside it and nothing on the page would say why.
    expect(spanOf(DEFAULT_PERIOD, NOW)).toBe(null)
  })

  it('names every period once', () => {
    const values = PERIODS.map((one) => one.value)
    expect(new Set(values).size).toBe(values.length)
  })
})

import { describe, expect, it } from 'vitest'
import { MOST, daysBetween, daysCovered, shiftDay } from '@/modules/onespace/lib/screen/spans'

const WINDOW = { since: '2026-03-01', until: '2026-03-31' }

describe('daysBetween', () => {
  it('counts the days from one to the other', () => {
    expect(daysBetween('2026-03-02', '2026-03-06')).toBe(4)
  })

  it('is nothing where there is no end, or the end is the start', () => {
    expect(daysBetween('2026-03-02', '')).toBe(0)
    expect(daysBetween('2026-03-02', '2026-03-02')).toBe(0)
  })

  it('is nothing where the end is before the start', () => {
    // Somebody typed it wrong. Drawing the span backwards would be inventing
    // days the record does not claim.
    expect(daysBetween('2026-03-06', '2026-03-02')).toBe(0)
  })

  it('reads a datetime as the day it falls on', () => {
    expect(daysBetween('2026-03-02 09:00:00', '2026-03-04 17:30:00')).toBe(2)
  })
})

describe('daysCovered', () => {
  it('is one day where nothing is covered', () => {
    expect(daysCovered('2026-03-04', 0, WINDOW)).toEqual(['2026-03-04'])
  })

  it('is every day of the span', () => {
    expect(daysCovered('2026-03-02', 4, WINDOW)).toEqual([
      '2026-03-02', '2026-03-03', '2026-03-04', '2026-03-05', '2026-03-06',
    ])
  })

  it('draws only the part of a span the month can show', () => {
    // A fortnight that starts in February: the month on screen is March, and
    // the four days of it that belong to March are what it can draw.
    expect(daysCovered('2026-02-26', 6, WINDOW)).toEqual([
      '2026-03-01', '2026-03-02', '2026-03-03', '2026-03-04',
    ])
  })

  it('stops at the end of the window rather than walking to the end of the span', () => {
    const found = daysCovered('2026-03-29', 30, WINDOW)
    expect(found).toEqual(['2026-03-29', '2026-03-30', '2026-03-31'])
  })

  it('still draws a span the window misses entirely', () => {
    // The row was fetched and belongs to this screen. A page of rows over an
    // empty month reads as a broken screen, not as a span scrolled past.
    expect(daysCovered('2026-01-04', 3, WINDOW)).toEqual(['2026-01-04'])
  })

  it('is bounded, so one mistyped year is not sixty thousand chips', () => {
    expect(daysCovered('2026-03-01', 100_000, {}).length).toBe(MOST)
  })

  it('says nothing about a date it cannot read', () => {
    expect(daysCovered('', 3, WINDOW)).toEqual([])
    expect(daysCovered('next Tuesday', 3, WINDOW)).toEqual([])
  })

  it('crosses a month end without arithmetic of its own', () => {
    expect(daysCovered('2026-02-27', 3, {})).toEqual([
      '2026-02-27', '2026-02-28', '2026-03-01', '2026-03-02',
    ])
  })
})

describe('shiftDay', () => {
  it('moves a day and stays a date', () => {
    expect(shiftDay('2026-03-30', 3)).toBe('2026-04-02')
    expect(shiftDay('2026-03-30', 0)).toBe('2026-03-30')
  })

  it('gives back what it was handed where that is not a date', () => {
    expect(shiftDay('', 3)).toBe('')
  })
})

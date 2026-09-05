import { describe, expect, it } from 'vitest'
import { MOST, occurrencesOf } from './recurrence'

const WINDOW = { since: '2026-03-01', until: '2026-03-31' }

describe('occurrencesOf', () => {
  it('is one day where nothing repeats', () => {
    expect(occurrencesOf('2026-03-04', '', '', WINDOW)).toEqual(['2026-03-04'])
    expect(occurrencesOf('2026-03-04', 'Fortnightly', '', WINDOW)).toEqual(['2026-03-04'])
  })

  it('reads the interval the way Frappe spells it', () => {
    expect(occurrencesOf('2026-03-04', 'Weekly', '', WINDOW)).toEqual([
      '2026-03-04', '2026-03-11', '2026-03-18', '2026-03-25',
    ])
  })

  it('stops where the rule says it stops', () => {
    expect(occurrencesOf('2026-03-04', 'Weekly', '2026-03-15', WINDOW)).toEqual([
      '2026-03-04', '2026-03-11',
    ])
  })

  it('walks past everything before the window rather than starting in it', () => {
    // A weekly meeting that began in 2019 is hundreds of occurrences before
    // the month on screen, and the ones in it are what was asked for.
    const found = occurrencesOf('2026-01-07', 'Weekly', '', WINDOW)
    // The original comes first whether or not it is in the window: a rule that
    // hid it would be a rule that moved the record.
    expect(found[0]).toBe('2026-01-07')
    expect(found.slice(1)).toEqual(['2026-03-04', '2026-03-11', '2026-03-18', '2026-03-25'])
  })

  it('crosses a month boundary by the day of the month', () => {
    expect(occurrencesOf('2026-01-31', 'Monthly', '', { since: '2026-01-01', until: '2026-04-30' }))
      .toEqual(['2026-01-31', '2026-03-03', '2026-03-31'])
  })

  it('is bounded', () => {
    const found = occurrencesOf('2020-01-01', 'Daily', '', {
      since: '2020-01-01', until: '2030-01-01',
    })
    expect(found).toHaveLength(MOST)
  })

  it('says nothing about a date it cannot read', () => {
    expect(occurrencesOf('', 'Daily', '', WINDOW)).toEqual([])
    expect(occurrencesOf('not a date', 'Daily', '', WINDOW)).toEqual([])
  })

  it('is one day with no window, because there is nothing to fill', () => {
    expect(occurrencesOf('2026-03-04', 'Weekly', '', {})).toEqual(['2026-03-04'])
  })
})

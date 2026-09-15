// A time of day, which is the one shape nothing else here can read.
//
// Frappe's `Time` is a MySQL `time` column, and the driver hands back a
// `timedelta` that serialises with its microseconds — `03:30:44.832953`. It is
// not a date, so dayjs calls it invalid, and every surface that asked what a
// Time said got the raw string. Six characters of noise in a list cell; the
// whole field on a read-only form, where an invoice's Posting Time read
// `3:30:44.832953` under a clock icon.
import { describe, expect, test } from 'vitest'
import { time } from '@/shared/lib/runtime/format'
import { cellText } from '@/modules/onespace/lib/screen/cells'

describe('a time of day with no day attached', () => {
  test('reads as a clock, microseconds and all', () => {
    expect(time('03:30:44.832953')).toBe('03:30:44')
  })

  test('pads an hour the server did not pad', () => {
    expect(time('3:30:44.832953')).toBe('03:30:44')
  })

  test('takes a value with no seconds on it', () => {
    expect(time('09:41')).toBe('09:41:00')
  })

  test('drops the seconds when asked, keeping the workspace pattern', () => {
    expect(time('03:30:44.832953', { toTheMinute: true })).toBe('03:30')
  })

  test('still reads a real datetime, which is what every other caller passes', () => {
    expect(time('2026-09-02 03:30:44')).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  // A `timedelta` is a duration, and MySQL will store `38:00:00` in a time
  // column. Anchoring that to a day rolls it over to 14:00 the next morning,
  // which is a wrong answer rather than an unformatted one.
  test('refuses a duration wearing the shape of a clock', () => {
    expect(time('38:00:00')).toBe('')
  })

  test('refuses what is not a clock at all', () => {
    expect(time('every Tuesday')).toBe('')
    expect(time('')).toBe('')
    expect(time(null)).toBe('')
  })
})

describe('the cell that draws one', () => {
  const column = { cell: 'time', fieldname: 'posting_time' }

  test('says the clock', () => {
    expect(cellText(column, '03:30:44.832953')).toBe('03:30:44')
  })

  // Rather than the empty string the formatter hands back: a value the reader
  // can see in the database is better said plainly than not said.
  test('says the raw value where there is no clock in it', () => {
    expect(cellText(column, '38:00:00')).toBe('38:00:00')
  })

  test('says nothing for nothing, like every other cell', () => {
    expect(cellText(column, '')).toBe('—')
  })
})

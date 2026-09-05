// Turning merged rows into what the grid draws.
//
// Every case here is one the server can send and a browser cannot easily be
// made to show: a whole day against a moment, an entry with no end, and the
// colour a source takes once there are more sources than colours.
import { beforeEach, describe, expect, it } from 'vitest'

import { COLOURS, colourFor, diary, diaryEvents, isOn, keyOf, showing, split, toggle } from './diary'

const SOURCES = [
  { key: 'event', label: 'Your diary' },
  { key: 'zzmock/events', label: 'Events' },
  { key: 'rua/visits', label: 'Site visits' },
]

const ROW = {
  id: 'zzmock/events/EV1',
  title: 'Quarterly review',
  start: '2026-09-10 10:00:00',
  end: '2026-09-10 11:30:00',
  kind: 'record',
  space: 'zzmock',
  screen: 'events',
  screen_label: 'Events',
  record: 'EV1',
}

describe('a date, and a time where there is one', () => {
  it('reads a Datetime as a moment', () => {
    expect(split('2026-09-10 10:00:00')).toEqual({ date: '2026-09-10', time: '10:00' })
  })

  it('reads a Date as a whole day', () => {
    expect(split('2026-09-10')).toEqual({ date: '2026-09-10', time: '' })
  })

  it('has nothing to say about an empty field', () => {
    expect(split('')).toBe(null)
    expect(split(null)).toBe(null)
  })
})

describe('what the grid gets', () => {
  it('carries the record across', () => {
    const [one] = diaryEvents([ROW], SOURCES)
    expect(one.id).toBe('zzmock/events/EV1')
    expect(one.title).toBe('Quarterly review')
    expect(one.fromDate).toBe('2026-09-10')
    expect(one.fromTime).toBe('10:00')
    expect(one.toTime).toBe('11:30')
    expect(one.isFullDay).toBe(false)
  })

  it('says which calendar it came from', () => {
    const [one] = diaryEvents([ROW], SOURCES)
    expect(one.venue).toBe('Events')
    expect(one.color).toBe(COLOURS[1])
  })

  it('gives a record with no end its own day and nothing more', () => {
    const [one] = diaryEvents([{ ...ROW, end: '' }], SOURCES)
    expect(one.toDate).toBe('2026-09-10')
    // Not an open-ended span running to whenever the next thing is.
    expect(one.toTime).toBe('10:00')
  })

  it('treats a Date field as a whole day', () => {
    const [one] = diaryEvents([{ ...ROW, start: '2026-09-10', end: '' }], SOURCES)
    expect(one.isFullDay).toBe(true)
    expect(one.fromTime).toBeUndefined()
  })

  it('drops a row whose date is empty rather than putting it on today', () => {
    expect(diaryEvents([{ ...ROW, start: '' }], SOURCES)).toHaveLength(0)
  })
})

describe('which colour a calendar takes', () => {
  it('is its place in the list, so the rail and the grid agree', () => {
    expect(colourFor('event', SOURCES)).toBe(COLOURS[0])
    expect(colourFor('rua/visits', SOURCES)).toBe(COLOURS[2])
  })

  it('wraps rather than running out', () => {
    const many = Array.from({ length: 9 }, (_, at) => ({ key: `s${at}` }))
    expect(colourFor('s7', many)).toBe(COLOURS[0])
  })

  it('falls back to the first for a source nobody declared', () => {
    expect(colourFor('gone', SOURCES)).toBe(COLOURS[0])
  })
})

describe('which calendars are on', () => {
  beforeEach(() => {
    diary.sources = SOURCES
    diary.off = []
  })

  it('is everything until somebody says otherwise', () => {
    expect(isOn('zzmock/events')).toBe(true)
    expect(showing([ROW])).toHaveLength(1)
  })

  it('switches one off and back on', () => {
    toggle('zzmock/events')
    expect(isOn('zzmock/events')).toBe(false)
    expect(showing([ROW])).toHaveLength(0)

    toggle('zzmock/events')
    expect(showing([ROW])).toHaveLength(1)
  })

  it('keys a personal event on its own row rather than on a screen', () => {
    expect(keyOf({ kind: 'event' })).toBe('event')
    expect(keyOf(ROW)).toBe('zzmock/events')
  })
})

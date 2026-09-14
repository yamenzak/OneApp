// How a state of presence is drawn, and what it is called.
//
// The ranking is the server's. What is decided here is the one thing the two
// halves split: `late` is a property of an `in` on the server and an entry of
// its own in the table, because the server should not carry a sixth state that
// means the same as one of the five and the page should not say "green, unless"
// in two places.
import { describe, expect, it } from 'vitest'

import {
  PRESENCE,
  dayLook,
  presenceLook,
  presenceSince,
} from '@/modules/onespace/lib/screen/presence'

describe('presenceLook', () => {
  it('draws a late arrival differently from an on-time one', () => {
    expect(presenceLook({ state: 'in', late: false })).toBe(PRESENCE.in)
    expect(presenceLook({ state: 'in', late: true })).toBe(PRESENCE.late)
  })

  it('does not colour approved leave like a problem', () => {
    // A manager scanning a team for trouble should not have their eye pulled to
    // the one absence that was agreed in advance.
    expect(PRESENCE.leave.theme).toBe('blue')
    expect(PRESENCE.absent.theme).toBe('red')
  })

  it('says it does not know rather than guessing', () => {
    expect(presenceLook(null)).toBe(PRESENCE.unknown)
    expect(presenceLook({})).toBe(PRESENCE.unknown)
    expect(presenceLook({ state: 'teleported' })).toBe(PRESENCE.unknown)
  })
})

describe('presenceSince', () => {
  it('is a time of day, where there is one', () => {
    // Frappe stamps `YYYY-MM-DD HH:MM:SS`, which Safari refuses to parse
    // without the T — hence the replace, and hence this test.
    expect(presenceSince({ since: '2026-09-14 09:41:00' })).toMatch(/9:41|09:41/)
  })

  it('says the minute and not the second', () => {
    // The workspace's own time format carries seconds because a log wants
    // them. "In · 09:41:07" reads as a timestamp; "In · 09:41" reads as a fact
    // about somebody's morning, which is what the pill is for.
    expect(presenceSince({ since: '2026-09-14 09:41:07' })).not.toMatch(/07\b/)
  })

  it('is nothing for a state that has no clock in it', () => {
    expect(presenceSince({ since: null })).toBe('')
    expect(presenceSince({})).toBe('')
    expect(presenceSince({ since: 'not a time' })).toBe('')
  })
})

describe('dayLook', () => {
  it('does not draw a day with no record like an absence', () => {
    // The two are not the same thing, and a strip that colours them alike lies
    // about somebody who had not joined yet.
    expect(dayLook('none').class).not.toBe(dayLook('absent').class)
  })

  it('does not draw a weekend like a gap either', () => {
    expect(dayLook('holiday').class).not.toBe(dayLook('none').class)
  })

  it('falls back to the gap for a state it has never heard of', () => {
    expect(dayLook('flooded')).toBe(dayLook('none'))
  })
})

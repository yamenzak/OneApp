// @vitest-environment node
//
// The fold and the unread mark, at the sizes a fixture cannot reach: the mail
// fixture is a thread of two, and folding does not begin until four of them
// have been read.
import { describe, expect, it } from 'vitest'

import { firstUnread, foldedRead } from './thread'

/** `rrru` — one letter a message, `r` read, `u` unread. */
const thread = (shape) =>
  [...shape].map((letter, at) => ({ name: `m${at}`, seen: letter === 'r' }))

const names = (set) => [...set].sort()

describe('folding a read run', () => {
  it('leaves a short thread alone', () => {
    expect(foldedRead(thread('rru'))).toEqual(new Set())
  })

  it('leaves four read messages alone when the last is one of them', () => {
    // Four read, but the last message is never in the run — so three, and
    // three is below the line.
    expect(foldedRead(thread('rrrr'))).toEqual(new Set())
  })

  it('folds the middle of five read messages, keeping the ends', () => {
    expect(names(foldedRead(thread('rrrrru')))).toEqual(['m1', 'm2', 'm3'])
  })

  it('never folds the message somebody came to read', () => {
    const folded = foldedRead(thread('rrrrrr'))
    expect(folded.has('m5')).toBe(false)
  })

  it('does not fold unread messages, however many there are', () => {
    expect(foldedRead(thread('uuuuuu'))).toEqual(new Set())
  })

  it('folds only what is above the new mail', () => {
    // m0-m3 read, m4 new, m5-m6 read again, m7 new. The run that folds is the
    // one above the mark; m5 and m6 stay, because a count that included them
    // would be describing messages on both sides of the line.
    const folded = foldedRead(thread('rrrrurru'))
    expect(names(folded)).toEqual(['m1', 'm2'])
  })
})

describe('where the new mail starts', () => {
  it('is the first unread message', () => {
    expect(firstUnread(thread('rruu'))).toBe('m2')
  })

  it('is nothing when the whole thread is new', () => {
    expect(firstUnread(thread('uuu'))).toBe(null)
  })

  it('is nothing when the whole thread has been read', () => {
    expect(firstUnread(thread('rrr'))).toBe(null)
  })

  it('marks the first, not the last, when unread messages are split', () => {
    expect(firstUnread(thread('urru'))).toBe('m0')
  })
})

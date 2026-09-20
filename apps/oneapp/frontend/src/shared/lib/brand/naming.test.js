import { describe, expect, it } from 'vitest'
import { theirs } from './naming'

/**
 * The question is the name, not the kind of thing.
 *
 * The switcher decided by kind — a space is somebody's, an app is ours — and
 * got the commonest case wrong in both states at once: OneHR is a space,
 * so the corner wrote it flat while the board one row down wrote it the family
 * way. These are the four cases that rule has to get right.
 */
describe('whether a name is somebody else’s', () => {
  it('is not, for a space still called what its mark is called', () => {
    expect(theirs('onehr', 'OneHR')).toBe(false)
    expect(theirs('onestorage', 'OneCloud')).toBe(false)
  })

  it('is, for a space a customer renamed', () => {
    expect(theirs('onehr', 'People')).toBe(true)
  })

  it('is, for an assistant a workspace named', () => {
    expect(theirs('oneai', 'Ada')).toBe(true)
  })

  it('is, for anything wearing no mark of ours', () => {
    expect(theirs('', 'RUA')).toBe(true)
    expect(theirs('nosuchmark', 'RUA')).toBe(true)
  })
})

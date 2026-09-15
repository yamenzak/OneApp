// What is open on the desk, and what one press of a tile means.
//
// The whole of this module is a list and an order, so the cases are about the
// order: that raising does not open, that opening twice does not open twice,
// and that a folded window is still there. `docs/UNIFICATION.md` F3 — the
// press is the guard everything else goes through, so it gets the most of them.

import { beforeEach, describe, expect, it } from 'vitest'

import {
  FLOOR, clear, close, desk, fold, inFront, onDesk, open, press, raise, shown, zOf,
} from './windows'

beforeEach(() => clear())

describe('opening', () => {
  it('puts a window on the desk and in front', () => {
    open('mail')
    expect(onDesk('mail')).toBe(true)
    expect(shown('mail')).toBe(true)
    expect(inFront('mail')).toBe(true)
  })

  it('does not open the same window twice', () => {
    // The assistant's shortcut, its dock tile and a record's own control all
    // call this, and two assistants is two conversations.
    open('assistant')
    open('assistant')
    expect(desk.open).toHaveLength(1)
  })

  it('brings a window that was behind back to the front', () => {
    open('mail')
    open('files')
    expect(inFront('mail')).toBe(false)
    open('mail')
    expect(inFront('mail')).toBe(true)
    expect(desk.open).toHaveLength(2)
  })

  it('unfolds one that was folded', () => {
    open('mail')
    fold('mail')
    expect(shown('mail')).toBe(false)
    open('mail')
    expect(shown('mail')).toBe(true)
  })
})

describe('the stack', () => {
  it('is the order of the list, so nothing is renumbered when one closes', () => {
    open('mail')
    open('files')
    open('assistant')
    expect(zOf('mail')).toBeLessThan(zOf('files'))
    expect(zOf('files')).toBeLessThan(zOf('assistant'))

    close('files')
    expect(zOf('mail')).toBe(FLOOR)
    expect(zOf('assistant')).toBe(FLOOR + 1)
  })

  it('answers the floor for a window nobody opened', () => {
    expect(zOf('nobody')).toBe(FLOOR)
  })

  it('will not raise a folded window', () => {
    // Raising something nobody can see is how a window comes to be open and
    // invisible with no way back to it.
    open('mail')
    open('files')
    fold('mail')
    raise('mail')
    expect(inFront('files')).toBe(true)
    expect(shown('mail')).toBe(false)
  })

  it('will not raise one that is not open', () => {
    open('mail')
    raise('files')
    expect(desk.open).toHaveLength(1)
    expect(inFront('mail')).toBe(true)
  })
})

describe('one press of a tile', () => {
  it('opens what was shut', () => {
    press('mail')
    expect(shown('mail')).toBe(true)
  })

  it('folds what is already in front', () => {
    // The only thing left to ask of a window you are looking at is to stop
    // looking at it.
    press('mail')
    press('mail')
    expect(onDesk('mail')).toBe(true)
    expect(shown('mail')).toBe(false)
  })

  it('raises what is open and behind, rather than folding it', () => {
    press('mail')
    press('files')
    press('mail')
    expect(shown('mail')).toBe(true)
    expect(inFront('mail')).toBe(true)
  })

  it('unfolds what was folded', () => {
    press('mail')
    press('mail')
    press('mail')
    expect(shown('mail')).toBe(true)
  })
})

describe('closing', () => {
  it('takes it off the desk', () => {
    open('mail')
    close('mail')
    expect(onDesk('mail')).toBe(false)
  })

  it('is quiet about a window that was never open', () => {
    expect(() => close('nobody')).not.toThrow()
  })

  it('leaves nothing in front when the last one goes', () => {
    open('mail')
    close('mail')
    expect(inFront('mail')).toBe(false)
  })
})

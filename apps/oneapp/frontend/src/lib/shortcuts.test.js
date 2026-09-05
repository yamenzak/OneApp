// @vitest-environment node
//
// The two rules a shortcut has to keep, at the level where they are decided.
// A browser pass can press `e` and watch a conversation archive; what it cannot
// do cheaply is press `e` inside forty different focused things and check that
// none of them archived anything.
import { describe, expect, it } from 'vitest'

import { isTyping, pressed } from './shortcuts'

const press = (key, held = {}) => pressed({ key, ...held })

describe('what was pressed', () => {
  it('is the letter, lowercased', () => {
    expect(press('e')).toBe('e')
    expect(press('E', { shiftKey: true })).toBe('shift+e')
  })

  it('names shift only where it changes which key it is', () => {
    // `?` is already a shifted press. Calling it `shift+?` would be describing
    // the keyboard rather than the press, and no shortcut table writes it.
    expect(press('?', { shiftKey: true })).toBe('?')
    expect(press('u', { shiftKey: true })).toBe('shift+u')
  })

  it('calls the platform modifier `mod`', () => {
    // Whichever this machine is, exactly one of the two counts — so the same
    // binding string works on both and neither picks a side.
    const both = [press('z', { metaKey: true }), press('z', { ctrlKey: true })]
    expect(both).toContain('mod+z')
    expect(both).toContain('z')
  })

  it('gives space a name, because a key called " " cannot be read', () => {
    expect(press(' ')).toBe('space')
  })

  it('survives an event with no key at all', () => {
    expect(pressed({})).toBe('')
  })
})

describe('where a shortcut must not fire', () => {
  it.each(['INPUT', 'TEXTAREA', 'SELECT'])('inside a %s', (tagName) => {
    expect(isTyping({ tagName })).toBe(true)
  })

  it('inside a rich editor, which is a div', () => {
    expect(isTyping({ tagName: 'DIV', isContentEditable: true })).toBe(true)
  })

  it('but does fire on an ordinary div', () => {
    expect(isTyping({ tagName: 'DIV' })).toBe(false)
  })

  it('and on nothing at all, which is what the body reports', () => {
    expect(isTyping(null)).toBe(false)
  })
})

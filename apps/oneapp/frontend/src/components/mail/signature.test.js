// @vitest-environment happy-dom
//
// Swapping a signature inside a body somebody is typing into. Every case here
// is one a person hits in an afternoon — changing the From on a half-written
// reply, replying to a thread, switching to an address that signs with nothing
// — and none of them is cheap to reach through a browser.
import { describe, expect, it } from 'vitest'

import { hasSignature, withSignature } from './signature'

const SIG = '<p>Hala — Al Reem</p>'
const OTHER = '<p>Sales — MockSpace</p>'
const QUOTE =
  '<p><br></p><p>On Tuesday, Hala wrote:</p><blockquote>The revised quote</blockquote>'

describe('putting one in', () => {
  it('adds it to an empty message', () => {
    const out = withSignature('', SIG)
    expect(out).toContain('Hala — Al Reem')
    expect(hasSignature(out)).toBe(true)
  })

  it('leaves somewhere to type above it', () => {
    // A composer whose only content is the signature puts the caret under it,
    // and the first thing anybody writes lands after their own sign-off.
    const out = withSignature('', SIG)
    expect(out.indexOf('<p>')).toBeLessThan(out.indexOf('Hala — Al Reem'))
  })

  it('keeps what somebody has typed', () => {
    const out = withSignature('<p>Thursday works.</p>', SIG)
    expect(out).toContain('Thursday works.')
    expect(out).toContain('Hala — Al Reem')
  })

  it('goes above the quoted history, not under three screens of it', () => {
    const out = withSignature(QUOTE, SIG)
    expect(out.indexOf('Hala — Al Reem')).toBeLessThan(out.indexOf('blockquote'))
  })

  it('goes above the attribution line too, which belongs to the quote', () => {
    const out = withSignature(QUOTE, SIG)
    expect(out.indexOf('Hala — Al Reem')).toBeLessThan(out.indexOf('On Tuesday'))
  })
})

describe('swapping one for another, after the editor has been at it', () => {
  // What the body looks like once ProseMirror has normalised it: our wrapper
  // is a plain paragraph and the class is gone. This is the case that matters —
  // anybody changing the From has typed something first.
  const EDITED = '<p><br></p><p>Thursday works.</p><p><br>Hala — Al Reem</p>'

  it('finds the old one by its words and swaps it', () => {
    const out = withSignature(EDITED, OTHER, SIG)
    expect(out).toContain('Sales — MockSpace')
    expect(out).not.toContain('Hala — Al Reem')
    expect(out).toContain('Thursday works.')
  })

  it('takes it away when the new address signs with nothing', () => {
    const out = withSignature(EDITED, '', SIG)
    expect(out).not.toContain('Hala — Al Reem')
    expect(out).toContain('Thursday works.')
  })

  it('leaves the quoted copy of the same words alone', () => {
    // Replying to somebody whose own sign-off is the same text as ours: theirs
    // is inside the quote, and eating it would be rewriting their message.
    const both =
      '<p><br>Hala — Al Reem</p><p>On Tuesday, Hala wrote:</p>' +
      '<blockquote><p>Yes</p><p>Hala — Al Reem</p></blockquote>'
    const out = withSignature(both, OTHER, SIG)
    expect(out).toContain('Sales — MockSpace')
    expect(out.match(/Hala — Al Reem/g)).toHaveLength(1)
  })

  it('adds the new one when the old is nowhere to be found', () => {
    // Somebody deleted it. Changing From then *adds* a signature rather than
    // silently sending none — which is what the address asked for.
    const out = withSignature('<p>Thursday works.</p>', OTHER, SIG)
    expect(out).toContain('Sales — MockSpace')
  })
})

describe('swapping one for another', () => {
  it('leaves one signature, not two', () => {
    const once = withSignature('<p>Thursday works.</p>', SIG)
    const twice = withSignature(once, OTHER, SIG)

    expect(twice).toContain('Sales — MockSpace')
    expect(twice).not.toContain('Hala — Al Reem')
    expect(twice).toContain('Thursday works.')
  })

  it('survives being asked for the same one twice', () => {
    const once = withSignature('<p>Hello.</p>', SIG)
    const twice = withSignature(once, SIG, SIG)
    expect(twice.match(/Al Reem/g)).toHaveLength(1)
  })

  it('takes it away when the new address signs with nothing', () => {
    const gone = withSignature(withSignature('<p>Hello.</p>', SIG), '', SIG)
    expect(gone).toContain('Hello.')
    expect(hasSignature(gone)).toBe(false)
  })

  it('treats whitespace as nothing, because an empty editor is not a signature', () => {
    expect(hasSignature(withSignature('<p>Hello.</p>', '   \n '))).toBe(false)
  })
})

describe('what it will not touch', () => {
  it('does not mistake a quoted signature for ours', () => {
    // The person being replied to has a signature too, and it is *in* the
    // quote. Swapping the From must not eat somebody else's sign-off.
    const theirs = '<blockquote><p>Hala — Al Reem</p></blockquote>'
    const out = withSignature(theirs, OTHER, SIG)
    expect(out).toContain('Hala — Al Reem')
    expect(out).toContain('Sales — MockSpace')
  })

  it('leaves a message with no signature alone when there is none to add', () => {
    expect(withSignature('<p>Just this.</p>', '')).toContain('Just this.')
  })
})

import { describe, expect, it } from 'vitest'

import { NARROW, narrowingFor, narrowingIn, sameNarrowing } from './narrowing'

describe('what a URL narrows a screen to', () => {
  it('reads one pair as one filter', () => {
    expect(narrowingIn({ [NARROW]: 'project:PROJ-0001' })).toEqual([
      ['project', '=', 'PROJ-0001'],
    ])
  })

  it('reads a pair of them as two filters', () => {
    // Which is how a Dynamic Link arrives: the id it points at, and the
    // doctype that id belongs to.
    expect(narrowingIn({ [NARROW]: 'about:PROJ-0001;about_doctype:One%20Project' })).toEqual([
      ['about', '=', 'PROJ-0001'],
      ['about_doctype', '=', 'One Project'],
    ])
  })

  it('reads a repeated key too, which is a link somebody edited', () => {
    expect(narrowingIn({ [NARROW]: ['about:PROJ-0001', 'about_doctype:One Project'] })).toEqual([
      ['about', '=', 'PROJ-0001'],
      ['about_doctype', '=', 'One Project'],
    ])
  })

  it('keeps a colon inside the value', () => {
    // Names are not ours: an Email Queue row or a URL in a title both carry
    // one, and splitting on every colon would narrow to half a name.
    expect(narrowingIn({ [NARROW]: 'link:https://example.com/a' })).toEqual([
      ['link', '=', 'https://example.com/a'],
    ])
  })

  it('round-trips a value carrying the separators', () => {
    const written = narrowingFor('project', 'A; B: C')
    expect(narrowingIn({ [NARROW]: written })).toEqual([['project', '=', 'A; B: C']])
  })

  it('drops what it cannot read rather than refusing', () => {
    // A truncated link should open the screen, not an error page.
    expect(narrowingIn({ [NARROW]: 'project' })).toEqual([])
    expect(narrowingIn({ [NARROW]: ':PROJ-0001' })).toEqual([])
    expect(narrowingIn({ [NARROW]: 'project:' })).toEqual([])
    expect(narrowingIn({})).toEqual([])
    expect(narrowingIn(null)).toEqual([])
  })
})

describe('what a tab puts in the link', () => {
  it('is the field and the record', () => {
    expect(narrowingFor('project', 'PROJ-0001')).toBe('project:PROJ-0001')
  })

  it("carries a Dynamic Link's doctype beside it", () => {
    expect(
      narrowingFor('about', 'PROJ-0001', [['about_doctype', '=', 'One Project']]),
    ).toBe('about:PROJ-0001;about_doctype:One%20Project')
  })

  it('leaves out a condition that is not an equality', () => {
    // The URL says "narrowed to this one". Anything else is a filter somebody
    // set, and belongs in the panel they set it in.
    expect(narrowingFor('project', 'PROJ-0001', [['status', '!=', 'Closed']]))
      .toBe('project:PROJ-0001')
  })

  it('is nothing without both halves', () => {
    expect(narrowingFor('', 'PROJ-0001')).toBe('')
    expect(narrowingFor('project', '')).toBe('')
  })
})

describe('whether two narrowings agree', () => {
  it('compares the filters and not the objects', () => {
    expect(sameNarrowing([['project', '=', 'A']], [['project', '=', 'A']])).toBe(true)
    expect(sameNarrowing([['project', '=', 'A']], [['project', '=', 'B']])).toBe(false)
    expect(sameNarrowing([], undefined)).toBe(true)
  })
})

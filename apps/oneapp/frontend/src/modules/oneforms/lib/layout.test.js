/**
 * Reading a flat list of rows as a page.
 *
 * The awkward cases are the point. A drag-and-drop builder produces a break
 * before any field, two breaks in a row and a trailing one constantly — nobody
 * is careful with a thing they are dragging — and each of them is a way to
 * draw an empty box on a page a stranger opened.
 */

import { describe, expect, it } from 'vitest'

import { isBreak, pageOf, pagesOf } from './layout.js'

const field = (fieldname) => ({ fieldname, fieldtype: 'Data', label: fieldname })
const page = { fieldtype: 'Page Break', fieldname: '', label: '' }
const column = { fieldtype: 'Column Break', fieldname: '', label: '' }
const section = (label) => ({ fieldtype: 'Section Break', fieldname: '', label })

describe('reading the rows', () => {
  it('is one page of one section when nothing says otherwise', () => {
    const [only, ...rest] = pagesOf([field('a'), field('b')])

    expect(rest).toHaveLength(0)
    expect(only.sections).toHaveLength(1)
    expect(only.sections[0].columns).toEqual([[field('a'), field('b')]])
  })

  it('starts a step at every page break', () => {
    const pages = pagesOf([field('a'), page, field('b'), page, field('c')])

    expect(pages).toHaveLength(3)
    expect(pages.map((one) => one.sections[0].columns[0][0].fieldname))
      .toEqual(['a', 'b', 'c'])
  })

  it('titles a section and keeps it inside its own step', () => {
    const [first, second] = pagesOf([
      section('About you'), field('a'),
      page,
      section('How to reach you'), field('b'), section('Anything else'), field('c'),
    ])

    expect(first.sections.map((one) => one.label)).toEqual(['About you'])
    expect(second.sections.map((one) => one.label))
      .toEqual(['How to reach you', 'Anything else'])
  })

  it('puts what follows a column break beside what came before', () => {
    const [only] = pagesOf([field('a'), column, field('b')])

    expect(only.sections[0].columns).toEqual([[field('a')], [field('b')]])
  })

  it('starts columns again in the next section', () => {
    const [only] = pagesOf([field('a'), column, field('b'), section('More'), field('c')])

    expect(only.sections[0].columns).toHaveLength(2)
    expect(only.sections[1].columns).toEqual([[field('c')]])
  })
})

describe('what a builder actually produces', () => {
  it('drops a page nobody put anything on', () => {
    // Two page breaks together, and one at the end. Both are one drag away.
    expect(pagesOf([field('a'), page, page, field('b'), page])).toHaveLength(2)
  })

  it('drops a heading with nothing under it', () => {
    const [only] = pagesOf([section('Empty'), section('Real'), field('a')])

    expect(only.sections.map((one) => one.label)).toEqual(['Real'])
  })

  it('drops a column nobody filled', () => {
    const [only] = pagesOf([field('a'), column, column, field('b')])

    expect(only.sections[0].columns).toEqual([[field('a')], [field('b')]])
  })

  it('is nothing at all for a form with no questions on it', () => {
    expect(pagesOf([])).toEqual([])
    expect(pagesOf([page, section('Nothing'), column])).toEqual([])
  })

  it('knows a break from a question', () => {
    expect(isBreak(page)).toBe(true)
    expect(isBreak(field('a'))).toBe(false)
    expect(isBreak(undefined)).toBe(false)
  })
})

describe('finding somebody their own mistake', () => {
  it('says which step a field is on', () => {
    const pages = pagesOf([field('a'), page, field('b'), page, field('c')])

    expect(pageOf(pages, 'c')).toBe(2)
    expect(pageOf(pages, 'a')).toBe(0)
  })

  it('says the first step for a field it cannot place', () => {
    // A refusal naming something the page does not draw is still a refusal
    // somebody has to read, and the top of the form is where they are looking.
    expect(pageOf(pagesOf([field('a')]), 'nonesuch')).toBe(0)
  })
})

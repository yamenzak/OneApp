/**
 * The half of the finder that needs no server.
 *
 * Going somewhere is answered out of the session payload, so the ranking and
 * the merge are ordinary functions over ordinary arrays — which is the whole
 * reason they are functions rather than computed properties inside the
 * component.
 */
import { describe, expect, it } from 'vitest'

import {
  ANYWHERE,
  EXACT,
  STARTS,
  WORD,
  merge,
  recordRow,
  routeFor,
  screensMatching,
  screensOf,
  where,
} from './finding'

const SPACES = [
  {
    space_code: 'onebook',
    space_label: 'OneBook',
    brand: 'onebook',
    screens: [
      { screen: 'invoices', label: 'Invoices', icon: 'lucide-receipt' },
      { screen: 'bills', label: 'Bills', icon: 'lucide-file-text' },
      { screen: 'configuration', label: 'Configuration' },
    ],
  },
  {
    space_code: 'onecrm',
    space_label: 'OneCRM',
    brand: 'onecrm',
    screens: [{ screen: 'deals', label: 'Deals', icon: 'lucide-handshake' }],
  },
]

describe('where', () => {
  it('ranks an exact match above a prefix above a word above anywhere', () => {
    expect(where('deals', 'Deals')).toBe(EXACT)
    expect(where('dea', 'Deals')).toBe(STARTS)
    expect(where('lost', 'Deals lost')).toBe(WORD)
    expect(where('eal', 'Deals')).toBe(ANYWHERE)
  })

  it('says nothing matched rather than ranking it last', () => {
    expect(where('zzz', 'Deals')).toBeGreaterThan(ANYWHERE)
  })

  it('ignores case and surrounding space on both sides', () => {
    expect(where('  DEALS ', 'deals')).toBe(EXACT)
  })
})

describe('screensOf', () => {
  it('flattens every space into one list, component screens included', () => {
    const found = screensOf(SPACES)
    expect(found).toHaveLength(4)
    expect(found[0]).toMatchObject({
      kind: 'screen', space: 'onebook', screen: 'invoices', title: 'Invoices',
    })
  })

  it('gives a screen with no icon one, so a row is never a gap', () => {
    expect(screensOf(SPACES)[2].icon).toBeTruthy()
  })

  it('answers nothing for a session that has not loaded', () => {
    expect(screensOf(undefined)).toEqual([])
  })
})

describe('screensMatching', () => {
  const screens = screensOf(SPACES)

  it('offers a few before anybody types', () => {
    expect(screensMatching(screens, '').length).toBe(4)
  })

  it('keeps only what matched, best first', () => {
    const found = screensMatching(screens, 'i')
    expect(found.map((one) => one.title)).toEqual(['Invoices', 'Bills', 'Configuration'])
  })

  it('matches the space as well as the screen', () => {
    expect(screensMatching(screens, 'onecrm').map((one) => one.screen)).toEqual(['deals'])
  })
})

describe('merge', () => {
  const hit = (over) => recordRow({
    doctype: 'Sales Invoice', name: 'INV-1', title: 'Invoice one',
    space: 'onebook', space_label: 'OneBook', screen: 'invoices',
    label: 'Invoice', rank: ANYWHERE, ...over,
  })

  it('puts a better match first whichever kind it is', () => {
    const rows = merge(
      [{ kind: 'screen', title: 'Invoices', rank: ANYWHERE }],
      [hit({ rank: EXACT, name: 'INV-2' })],
    )
    expect(rows[0].kind).toBe('record')
  })

  it('puts a screen ahead of a record at the same rank', () => {
    const rows = merge(
      [{ kind: 'screen', title: 'Invoices', rank: STARTS }],
      [hit({ rank: STARTS })],
    )
    expect(rows.map((one) => one.kind)).toEqual(['screen', 'record'])
  })

  it('keeps the order the server sent inside one rank', () => {
    const rows = merge([], [
      hit({ name: 'INV-1', rank: WORD }),
      hit({ name: 'INV-2', rank: WORD }),
    ])
    expect(rows.map((one) => one.name)).toEqual(['INV-1', 'INV-2'])
  })
})

describe('routeFor', () => {
  it('sends a screen to its space with the screen in the query', () => {
    expect(routeFor({ kind: 'screen', space: 'onebook', screen: 'invoices' })).toEqual({
      name: 'Screen',
      params: { spaceCode: 'onebook' },
      query: { screen: 'invoices' },
    })
  })

  it('sends a record to the same place with the record open', () => {
    const to = routeFor({
      kind: 'record', space: 'onebook', screen: 'invoices', name: 'INV-0007',
    })
    expect(to.params).toEqual({ spaceCode: 'onebook' })
    expect(to.query.screen).toBe('invoices')
    expect(to.query.at).toBe('record:INV-0007')
  })
})

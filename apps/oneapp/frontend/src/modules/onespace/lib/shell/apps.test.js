import { describe, expect, it } from 'vitest'
import { ADD, CATALOGUE, HERE, OFF, SOON, SPACE, SURFACE, stateOf } from './apps'
import { MARKS } from '@/shared/lib/brand/marks'

/**
 * The catalogue is a declaration, so what is worth testing about it is that it
 * is a *complete* one: every entry draws, every entry is reachable or says why
 * not, and nothing is in it twice.
 *
 * The state machine is four lines and is tested anyway, because it is the
 * whole of "disabled, with the reason" — §F1 — and the failure mode is a tile
 * that looks pressable and is not.
 */

describe('the catalogue', () => {
  it('names a mark this build actually has', () => {
    for (const app of CATALOGUE) {
      expect(MARKS[app.brand], `${app.brand} is not a mark`).toBeTruthy()
    }
  })

  it('names each app once', () => {
    const seen = CATALOGUE.map((one) => one.brand)
    expect(new Set(seen).size).toBe(seen.length)
  })

  it('gives every built app somewhere to go', () => {
    for (const app of CATALOGUE.filter((one) => one.kind === SURFACE)) {
      expect(app.to?.name, `${app.brand} is built and goes nowhere`).toBeTruthy()
      expect(typeof app.live).toBe('function')
    }
  })

  it('makes every app that can be switched off say why', () => {
    // The ones whose `live` is not a constant `true` are the ones a workspace
    // can be without — Mail with no address, the assistant switched off — and
    // a dim tile with no reason on it is the facet-with-no-explanation §B2
    // spent a section on.
    for (const app of CATALOGUE.filter((one) => one.kind === SURFACE)) {
      if (app.live()) continue
      expect(app.why, `${app.brand} can be off and does not say why`).toBeTruthy()
    }
  })

  it("gives the rail's foot four surfaces, not seven", () => {
    // The three editors are reached through the Drive place that holds what
    // they make, so they are on the board and not in the 3rem column.
    const quick = CATALOGUE.filter((one) => one.quick)
    expect(quick.map((one) => one.brand)).toEqual([
      'onemail', 'onecalendar', 'onestorage', 'oneai',
    ])
  })
})

describe('what a workspace has of one', () => {
  const held = new Set(['onehr'])

  it('is here for a space this workspace holds', () => {
    expect(stateOf({ kind: SPACE, brand: 'onehr' }, held)).toBe(HERE)
  })

  it('is addable for one it does not', () => {
    expect(stateOf({ kind: SPACE, brand: 'onecrm' }, held)).toBe(ADD)
  })

  it('is here for a surface that is switched on', () => {
    expect(stateOf({ kind: SURFACE, live: () => true }, held)).toBe(HERE)
  })

  it('is off for one that is not', () => {
    expect(stateOf({ kind: SURFACE, live: () => false }, held)).toBe(OFF)
  })

  it('is never on for something nobody has built', () => {
    // Including one that declares a route by mistake: a drawing is not an app.
    expect(stateOf({ kind: SOON, brand: 'onetask', live: () => true }, held)).toBe(SOON)
  })
})

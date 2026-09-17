import { describe, expect, it } from 'vitest'
import { ADD, CATALOGUE, HERE, OFF, SERVICE, SOON, SPACE, stateOf } from './apps'
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

/** The services this workspace could actually reach — see `stateOf`. */
const built = (one) => one.kind === SERVICE && one.built !== false

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
    for (const app of CATALOGUE.filter(built)) {
      expect(app.to?.name, `${app.brand} is built and goes nowhere`).toBeTruthy()
      expect(typeof app.live).toBe('function')
    }
  })

  it('makes every app that can be switched off say why', () => {
    // The ones whose `live` is not a constant `true` are the ones a workspace
    // can be without — Mail with no address, the assistant switched off — and
    // a dim tile with no reason on it is the facet-with-no-explanation §B2
    // spent a section on.
    for (const app of CATALOGUE.filter(built)) {
      if (app.live()) continue
      expect(app.why, `${app.brand} can be off and does not say why`).toBeTruthy()
    }
  })

  it("gives the dock seven services, not eight", () => {
    // It was four, and the two editors joined them when a document and a
    // workbook became things you open rather than places you go — a window of
    // their own, over whatever you were reading. A tile is what opens one, so
    // a tile is what they need.
    //
    // OneTask is the seventh, since `docs/WORK.md` §12: it is a service over
    // ERPNext's Task rather than a space, and catching a thought without
    // leaving the page you are on is the definition of what a dock tile is
    // for.
    //
    // OneCode is the eighth and stays off: there is nothing to open yet, and
    // a dock tile for a thing that only lands you in a folder is a tile that
    // says the same as the one beside it.
    const quick = CATALOGUE.filter((one) => one.quick)
    expect(quick.map((one) => one.brand)).toEqual([
      'onemail', 'onecalendar', 'onestorage', 'oneai', 'onedoc', 'onesheet',
      'onetask',
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
    expect(stateOf({ kind: SERVICE, live: () => true }, held)).toBe(HERE)
  })

  it('is off for one that is not', () => {
    expect(stateOf({ kind: SERVICE, live: () => false }, held)).toBe(OFF)
  })

  it('is never on for something nobody has built', () => {
    // Including one that declares a route by mistake: a drawing is not an app.
    expect(stateOf({ kind: SERVICE, built: false, brand: 'onetask', live: () => true }, held)).toBe(SOON)
  })
})

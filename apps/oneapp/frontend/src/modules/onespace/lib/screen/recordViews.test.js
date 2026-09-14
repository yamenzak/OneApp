// Which page draws one record, read off the resolved spec.
//
// The engine has already narrowed the name — `onespace/recordviews.py` — so
// what is checked here is that the browser reads rather than decides: the two
// halves deciding separately is how a screen becomes one thing in the rail and
// another when it opens.
import { describe, expect, it } from 'vitest'

import {
  DEFAULT_RECORD_VIEW,
  RECORD_VIEWS,
  recordBodyFor,
  recordViewOf,
} from '@/modules/onespace/lib/screen/recordViews'

const spec = (as) => ({ view_settings: as === undefined ? {} : { record: { as } } })

describe('recordViewOf', () => {
  it('is the form and the tabs when a screen says nothing', () => {
    expect(recordViewOf(spec())).toBe(DEFAULT_RECORD_VIEW)
    expect(recordViewOf({})).toBe(DEFAULT_RECORD_VIEW)
    expect(recordViewOf(null)).toBe(DEFAULT_RECORD_VIEW)
  })

  it('is what the screen named', () => {
    expect(recordViewOf(spec('person'))).toBe('person')
    expect(recordViewOf(spec('showcase'))).toBe('showcase')
  })

  it('falls back rather than drawing nothing', () => {
    // A name this build does not have is a manifest that ran ahead of a
    // deploy. The screen keeps the page it had and gets the new one the day it
    // exists — the same rule an unknown view type follows.
    expect(recordViewOf(spec('hologram'))).toBe(DEFAULT_RECORD_VIEW)
    expect(recordViewOf(spec(''))).toBe(DEFAULT_RECORD_VIEW)
  })
})

describe('the table itself', () => {
  it('mounts nothing for the default, which is RecordView’s own body', () => {
    expect(recordBodyFor('record')).toBe(null)
    expect(recordBodyFor('hologram')).toBe(null)
  })

  it('has a component for everything else', () => {
    for (const [name, one] of Object.entries(RECORD_VIEWS)) {
      if (name === DEFAULT_RECORD_VIEW) continue
      expect(typeof one.body, name).toBe('function')
    }
  })
})

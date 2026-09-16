// @vitest-environment node
//
// What the assistant is about, once a desk can hold several things at once.
//
// This was one claim and the last writer won, which was sound while a surface
// was a page: there was only ever one. Windows made it a guess, and then
// front-most made it a better guess — and a guess either way, silent in both
// directions. What is held here is the answer that replaced it: every claim
// counts, the desk gives the order, and the person switches off what they do
// not want carried.

import { effectScope } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/** The desk, stubbed: `frontToBack` is its order and this is what it says. */
const stack = { ids: [] }

vi.mock('@/modules/onespace/lib/desk/windows', () => ({
  WINDOW_ID: Symbol('window-id'),
  frontToBack: () => stack.ids,
}))

let mod
let inside = null

// `inject` is what tells a claim which window it is in, and there is no
// component tree here. Mocking it is mocking the one line of Vue this module
// uses that a scope alone does not provide.
vi.mock('vue', async () => {
  const real = await vi.importActual('vue')
  return { ...real, inject: () => inside }
})

beforeEach(async () => {
  vi.resetModules()
  stack.ids = []
  inside = null
  mod = await import('./context')
})

/** Claim something from inside `owner`, and keep the scope so it stays. */
function claim(owner, said) {
  const scope = effectScope()
  inside = owner
  scope.run(() => mod.useAiContext(() => said))
  inside = null
  return scope
}

describe('what is open', () => {
  it('is everything with something to say, front-first', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    claim('file:B', { file: 'B', label: 'Workbook' })
    claim(null, { space: 'rua', screen: 'projects', label: 'Projects' })
    stack.ids = ['file:B', 'file:A']

    expect(mod.openContexts(null, null).map((one) => one.label))
      .toEqual(['Workbook', 'Letter', 'Projects'])
  })

  it('leaves out a window that has been folded away', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    claim('file:B', { file: 'B', label: 'Workbook' })
    // `frontToBack` drops the folded ones, which is the whole of how putting a
    // window away stops the assistant being about it.
    stack.ids = ['file:A']

    expect(mod.openContexts(null, null).map((one) => one.label)).toEqual(['Letter'])
  })

  it('reads the page from the route where the page declared nothing', () => {
    const fromRoute = () => ({ space: 'rua', screen: 'projects', label: 'Projects' })
    expect(mod.openContexts({}, fromRoute).map((one) => one.label)).toEqual(['Projects'])
  })

  it('counts one thing once, however many ways it is open', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    stack.ids = ['file:A']
    const fromRoute = () => ({ file: 'A', label: 'Letter, as the page' })

    // A document open in a window and open as the page is one document. The
    // window's entry wins, being the one in front.
    expect(mod.openContexts({}, fromRoute).map((one) => one.label)).toEqual(['Letter'])
  })

  it('forgets a claim when its surface goes', () => {
    const scope = claim('file:A', { file: 'A', label: 'Letter' })
    stack.ids = ['file:A']
    expect(mod.openContexts(null, null)).toHaveLength(1)

    scope.stop()
    expect(mod.openContexts(null, null)).toHaveLength(0)
  })
})

describe('which of it goes with the question', () => {
  it('is all of it until somebody says otherwise', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    claim('file:B', { file: 'B', label: 'Workbook' })
    stack.ids = ['file:A', 'file:B']

    expect(mod.includedContexts(null, null)).toHaveLength(2)
    expect(mod.openContexts(null, null).every((one) => one.on)).toBe(true)
  })

  it('drops the one switched off, and keeps it on the list', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    claim('file:B', { file: 'B', label: 'Workbook' })
    stack.ids = ['file:A', 'file:B']

    mod.toggleContext('file:A')

    // Still drawn — a chip you cannot see is a chip you cannot switch back on.
    expect(mod.openContexts(null, null).map((one) => one.on)).toEqual([false, true])
    expect(mod.includedContexts(null, null).map((one) => one.file)).toEqual(['B'])

    mod.toggleContext('file:A')
    expect(mod.includedContexts(null, null)).toHaveLength(2)
  })

  it('switches something newly opened on', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    stack.ids = ['file:A']
    mod.toggleContext('file:A')

    claim('file:B', { file: 'B', label: 'Workbook' })
    stack.ids = ['file:A', 'file:B']

    // Off is what is remembered, so anything that arrives later arrives on.
    // The alternative is a person having to switch on every window they open,
    // which is the choosing this was built to avoid.
    expect(mod.includedContexts(null, null).map((one) => one.file)).toEqual(['B'])
  })
})

describe('the one in front', () => {
  it('is what declaredNow answers, skipping a window with nothing to say', () => {
    claim('file:A', { file: 'A', label: 'Letter' })
    claim('file:B', null)
    stack.ids = ['file:B', 'file:A']

    expect(mod.declaredNow().file).toBe('A')
  })

  it('falls back to the route where no window declares one', () => {
    const fromRoute = () => ({ space: 'rua', screen: 'projects', label: 'Projects' })
    expect(mod.openContext({}, fromRoute).label).toBe('Projects')
  })
})

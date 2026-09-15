// Which preview is in front, and in what order the dock lists them.
//
// The question is the whole of why this is tested without a browser: several
// peeks are several fetches, and the first build let whichever *returned* last
// take the front — so the same address drew a different window each time it
// was opened. The answer has to come from the URL, and a test that can settle
// two promises in the wrong order on purpose is the one that proves it does.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive } from 'vue'

const records = {}
const specs = {}

vi.mock('@/shared/lib/workspace', () => ({
  workspace: {
    screenRecord: (space, screen, name) => records[`${screen}/${name}`],
    screenSpec: (space, screen) => specs[screen],
  },
}))

const { usePeek, RECORD } = await import('./usePeek')
const { clear, desk } = await import('@/modules/onespace/lib/desk/windows')

/** A record the server would answer with, and a screen to draw it through. */
const seed = (screen, name, title) => {
  records[`${screen}/${name}`] = { name, title_field_value: title, label: title }
  specs[screen] = { screen, doctype: 'Thing', title_field: 'label' }
}

/** The composable, running inside a scope so its watchers can be torn down. */
function open(at) {
  const route = reactive({ query: { screen: 'invoices', at } })
  const scope = effectScope()
  const api = scope.run(() => usePeek({
    spaceCode: 'rua',
    spec: { value: { screen: 'invoices' } },
    route,
    router: { push: (to) => { route.query = to.query }, replace: () => {} },
    reloadList: () => {},
  }))
  return { ...api, route, stop: () => scope.stop() }
}

/** Every record window on the desk, back to front. */
const windows = () => desk.open.filter((one) => one.id.startsWith(RECORD)).map((one) => one.id)

beforeEach(() => {
  clear()
  seed('clients', 'CL-0003', 'zzMeridian Group')
  seed('projects', 'PR-0002', 'Harbour Point')
})

describe('several peeks open at once', () => {
  it('lists them in the order the URL stacked them', async () => {
    const { stop } = open('record:INV-0007|peek:clients/CL-0003|peek:projects/PR-0002')
    await nextTick()
    await nextTick()
    expect(windows()).toEqual([`${RECORD}clients/CL-0003`, `${RECORD}projects/PR-0002`])
    stop()
  })

  it('puts the innermost one in front, whichever fetch answered last', async () => {
    // The client's record resolves a tick after the project's, which is the
    // race that used to decide this.
    records['clients/CL-0003'] = new Promise((done) => {
      setTimeout(() => done({ name: 'CL-0003', label: 'zzMeridian Group' }), 5)
    })
    const { front, stop } = open('record:INV-0007|peek:clients/CL-0003|peek:projects/PR-0002')
    await new Promise((done) => { setTimeout(done, 20) })
    expect(front.value?.key).toBe(`${RECORD}projects/PR-0002`)
    stop()
  })

  it('draws one of them, because they share a corner', async () => {
    const { peeks, front, stop } = open('record:INV-0007|peek:clients/CL-0003|peek:projects/PR-0002')
    await new Promise((done) => { setTimeout(done, 20) })
    expect(peeks.value.length).toBe(2)
    expect(peeks.value.filter((one) => one.key === front.value?.key).length).toBe(1)
    stop()
  })
})

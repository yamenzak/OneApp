// @vitest-environment node
//
// The one question this file settles: who gets asked. A menu asks once for
// the whole session, and a stranger following a share link is not asked at
// all — they have no workspace, so the endpoint would answer 403 and put a
// failed request in the console of a page that is meant to be a document and
// nothing else.

import { describe, expect, it, vi } from 'vitest'

const aiVerbs = vi.fn()
const through = vi.fn(() => false)

vi.mock('@/shared/lib/workspace', () => ({
  workspace: { aiVerbs: (...args) => aiVerbs(...args) },
}))

// Mocked rather than driven through `window.location`: `throughLink` reads
// the address bar, the suite runs in node, and what this file is about is
// what `verbs.js` does with the answer.
vi.mock('@/shared/lib/live/link', () => ({ throughLink: () => through() }))

async function fresh({ link = false } = {}) {
  vi.resetModules()
  aiVerbs.mockReset()
  aiVerbs.mockResolvedValue({ live: true, rewrite: true, verbs: ['improve'], tones: [] })
  through.mockReturnValue(link)
  return (await import('./verbs')).writingVerbs
}

describe('writingVerbs', () => {
  it('ships closed, so a menu mounted first draws nothing', async () => {
    const writingVerbs = await fresh()
    const state = writingVerbs()

    expect(state.live).toBe(false)
    expect(state.verbs).toEqual([])
  })

  it('asks once however many menus there are', async () => {
    const writingVerbs = await fresh()
    writingVerbs()
    writingVerbs()
    writingVerbs()

    expect(aiVerbs).toHaveBeenCalledTimes(1)
  })

  it('opens up when the answer lands', async () => {
    const writingVerbs = await fresh()
    const state = writingVerbs()
    await Promise.resolve()
    await Promise.resolve()

    expect(state.live).toBe(true)
    expect(state.verbs).toEqual(['improve'])
  })

  it('stays closed when the gateway is unreachable', async () => {
    const writingVerbs = await fresh()
    aiVerbs.mockRejectedValue(new Error('nope'))
    const state = writingVerbs()
    await Promise.resolve()
    await Promise.resolve()

    expect(state.live).toBe(false)
  })

  it('does not ask at all through a share link', async () => {
    const writingVerbs = await fresh({ link: true })
    const state = writingVerbs()

    expect(aiVerbs).not.toHaveBeenCalled()
    expect(state.live).toBe(false)
  })

  it('stays closed through a link even after the answer would have landed', async () => {
    const writingVerbs = await fresh({ link: true })
    const state = writingVerbs()
    await Promise.resolve()
    await Promise.resolve()

    expect(state.live).toBe(false)
  })
})

/**
 * Watching one AI answer arrive.
 *
 * Three of these are about frames that did not arrive, which is the whole
 * reason this composable is more than a `socket.on`: realtime is best-effort,
 * and every way it can drop something ends with text that is quietly wrong or
 * a glow that never stops.
 */

import { effectScope } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** The socket, replaced by something a test can push messages through. */
const listeners = new Map()
vi.mock('@/shared/lib/runtime/socket', () => ({
  onEvent: (event, handler) => {
    if (!listeners.has(event)) listeners.set(event, new Set())
    listeners.get(event).add(handler)
    return () => listeners.get(event).delete(handler)
  },
}))

const server = { result: vi.fn(), stop: vi.fn() }
vi.mock('@/shared/lib/workspace', () => ({
  workspace: {
    aiResult: (run) => server.result(run),
    aiStop: (run) => server.stop(run),
  },
}))

const { CHANNEL, useAiRun } = await import('@/shared/lib/ai/run')

/** What the server would have published. */
const publish = (message) =>
  listeners.get(CHANNEL)?.forEach((fn) => fn(message))

/** A scope, because the composable disposes its listener in one. */
let scope
const inScope = (fn) => scope.run(fn)

/**
 * Let `start` get as far as subscribing.
 *
 * A macrotask rather than a couple of `Promise.resolve()`: start awaits the
 * POST and then the catch-up fetch, and counting the microtasks between them
 * is a test that breaks the next time a line moves.
 */
const subscribed = () => new Promise((done) => setTimeout(done, 0))

beforeEach(() => {
  scope = effectScope()
  server.result.mockReset()
  server.stop.mockReset()
  server.stop.mockResolvedValue({ ok: true })
  // The default: the catch-up fetch finds the run still going.
  server.result.mockResolvedValue({ state: 'running', text: '' })
})

afterEach(() => scope.stop())

describe('a run', () => {
  it('accumulates the deltas as they land', async () => {
    const ai = inScope(() => useAiRun())
    const done = ai.start(async () => ({ ok: true, run: 'r1' }))
    await subscribed()

    publish({ run: 'r1', delta: 'The quote ' })
    publish({ run: 'r1', delta: 'still holds.' })

    expect(ai.text.value).toBe('The quote still holds.')
    expect(ai.running.value).toBe(true)

    publish({ run: 'r1', done: true, state: 'done', text: 'The quote still holds.', credits: 2 })

    await expect(done).resolves.toBe('The quote still holds.')
    expect(ai.running.value).toBe(false)
    expect(ai.credits.value).toBe(2)
  })

  it('takes the whole text off the final frame, not what it accumulated', async () => {
    // The case this exists for: a dropped frame in the middle. Without the
    // final frame carrying the whole answer, that is a sentence with a hole
    // in it that nothing ever fixes.
    const ai = inScope(() => useAiRun())
    const done = ai.start(async () => ({ ok: true, run: 'r2' }))
    await subscribed()

    publish({ run: 'r2', delta: 'The quote ' })
    publish({ run: 'r2', done: true, state: 'done', text: 'The quote still holds.' })

    await done
    expect(ai.text.value).toBe('The quote still holds.')
  })

  it('ignores frames belonging to another run', async () => {
    const one = inScope(() => useAiRun())
    const two = inScope(() => useAiRun())
    one.start(async () => ({ ok: true, run: 'a' }))
    two.start(async () => ({ ok: true, run: 'b' }))
    await subscribed()

    publish({ run: 'a', delta: 'mine' })

    expect(one.text.value).toBe('mine')
    expect(two.text.value).toBe('')
  })

  it('catches up on a run that finished before anyone was listening', async () => {
    // Between the POST returning and the handler attaching, a short run can
    // finish and publish to nobody at all.
    server.result.mockResolvedValue({ state: 'done', text: 'Already written.', credits: 1 })

    const ai = inScope(() => useAiRun())
    await expect(ai.start(async () => ({ ok: true, run: 'r3' }))).resolves.toBe('Already written.')
    expect(ai.running.value).toBe(false)
    expect(ai.text.value).toBe('Already written.')
  })

  it('carries whatever else the feature returned', async () => {
    const ai = inScope(() => useAiRun())
    const done = ai.start(async () => ({ ok: true, run: 'r4' }))
    await subscribed()

    publish({
      run: 'r4', done: true, state: 'done', text: 'Read it.',
      actions: [{ kind: 'todo', title: 'Send the schedule' }],
    })

    await done
    expect(ai.extra.value.actions).toHaveLength(1)
  })

  it('stops running when the server refuses to start', async () => {
    const ai = inScope(() => useAiRun())
    await ai.start(async () => ({ ok: false, reason: 'disabled', message: 'Switched off.' }))

    expect(ai.running.value).toBe(false)
    expect(ai.error.value).toBe('Switched off.')
  })

  it('reports a failure rather than glowing forever', async () => {
    const ai = inScope(() => useAiRun())
    const done = ai.start(async () => ({ ok: true, run: 'r5' }))
    await subscribed()

    publish({ run: 'r5', done: true, state: 'failed', message: 'That did not work.' })

    await done
    expect(ai.running.value).toBe(false)
    expect(ai.error.value).toBe('That did not work.')
  })

  it('keeps what arrived when it is cancelled', async () => {
    const ai = inScope(() => useAiRun())
    const done = ai.start(async () => ({ ok: true, run: 'r6' }))
    await subscribed()

    publish({ run: 'r6', delta: 'As far as' })
    await ai.stop()
    publish({ run: 'r6', done: true, state: 'cancelled', text: 'As far as' })

    await done
    expect(server.stop).toHaveBeenCalledWith('r6')
    expect(ai.text.value).toBe('As far as')
    // Cancelled is not an error: somebody asked for it.
    expect(ai.error.value).toBe('')
  })

  it('lets go of the run when its scope does', async () => {
    const ai = inScope(() => useAiRun())
    ai.start(async () => ({ ok: true, run: 'r7' }))
    await subscribed()

    scope.stop()
    publish({ run: 'r7', delta: 'too late' })

    expect(ai.text.value).toBe('')
  })
})

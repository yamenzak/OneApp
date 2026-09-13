/**
 * What a room does when nobody answers.
 *
 * This is the case that had no witness and so went wrong quietly: the join was
 * an un-deadlined promise, so a socket that never connects left it pending for
 * ever. `useLiveDocument` awaits that promise before it decides which
 * extensions the editor is built with, so the editor never mounted at all — a
 * document opened as a header, a word count and a blank page, on any site
 * whose `/socket.io` was not reachable.
 *
 * The happy path is not here. It needs the relay, which is `relay.test.js`
 * against the handlers and a two-browser e2e above that; what is worth holding
 * in a unit test is the refusal and the giving up, because both are paths a
 * person only reaches when something else is already broken.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** A socket that takes an emit and never acks, like one that cannot connect. */
const silent = { on: () => {}, emit: () => {} }

/** A socket that acks straight away, with whatever the relay would have said. */
const answering = (answer) => ({
  on: () => {},
  emit: (event, kind, name, ack) => ack(answer),
})

let socket = silent
vi.mock('@/shared/lib/runtime/socket', () => ({ getSocket: () => socket }))

// A fresh module per test: `joinRoom` reference-counts what this tab has asked
// for in module state, so two tests sharing it would share a seat.
const fresh = async () => {
  vi.resetModules()
  return import('./room.js')
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  socket = silent
})

describe('joining a room', () => {
  it('gives up rather than hanging when the socket never answers', async () => {
    socket = silent
    const { joinRoom } = await fresh()

    const joining = joinRoom('file', 'FILE-1')
    let settled = false
    joining.then(() => { settled = true })

    // Before the deadline it is still hoping, which is the point of having one
    // at all: a slow connection collaborates rather than opening alone.
    await vi.advanceTimersByTimeAsync(7000)
    expect(settled).toBe(false)

    await vi.advanceTimersByTimeAsync(2000)
    expect(await joining).toBe(null)
  })

  it('lets the next open ask again', async () => {
    socket = silent
    const { joinRoom } = await fresh()

    const first = joinRoom('file', 'FILE-1')
    await vi.advanceTimersByTimeAsync(9000)
    expect(await first).toBe(null)

    // The seat is not cached as "refused". Somebody who reloads once the relay
    // is back gets a room — if the failed ask were kept, a site would stay
    // solo until every tab was closed.
    socket = answering({ ok: true, room: 'file/FILE-1', write: true, who: { user: 'a@b.test' } })
    const second = await joinRoom('file', 'FILE-1')
    expect(second?.name).toBe('file/FILE-1')
  })

  it('is nothing when the server will not have us', async () => {
    socket = answering({ ok: false })
    const { joinRoom } = await fresh()
    expect(await joinRoom('file', 'FILE-1')).toBe(null)
  })
})

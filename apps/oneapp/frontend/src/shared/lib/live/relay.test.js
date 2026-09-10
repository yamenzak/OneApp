/**
 * The socket relay's refusals.
 *
 * `apps/oneapp/realtime/handlers.js` runs inside Frappe's socketio process,
 * which no suite here can start, so it is driven directly with a fake socket.
 * What is worth testing is not the happy path — the two-browser e2e covers
 * that — but the three things that would each be a hole: a client naming its
 * own room, a reader writing, and one socket pushing a room's worth of memory
 * through the process.
 */

import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { describe, expect, it, beforeEach } from 'vitest'

const here = dirname(fileURLToPath(import.meta.url))
const handlers = createRequire(import.meta.url)(
  resolve(here, '../../../../../realtime/handlers.js'),
)

/** A socket the handler can be attached to, with everything it reaches. */
function fakeSocket({ admit, link = '', id = 'sock-1' } = {}) {
  const on = new Map()
  const sent = []
  const joined = new Set()
  const asked = []
  const sock = {
    id,
    user: 'someone@example.test',
    // What a page opened at `/one/link/<secret>` puts in the handshake. A
    // browser cannot set headers on a websocket, so this is where a guest's
    // only credential can travel.
    handshake: { query: link ? { oneapp_link: link } : {} },
    asked,
    emit: (event, payload) => sent.push({ to: 'self', event, payload }),
    join: (room) => joined.add(room),
    leave: (room) => joined.delete(room),
    on: (event, fn) => on.set(event, fn),
    fire: (event, ...args) => on.get(event)?.(...args),
    frappe_request: async (path, args) => {
      asked.push({ path, args })
      return { json: async () => ({ message: admit }) }
    },
    to: (room) => ({
      emit: (event, payload) => sent.push({ to: room, event, payload }),
    }),
    nsp: {
      adapter: { rooms: new Map() },
      sockets: new Map(),
      to: (room) => ({
        emit: (event, payload) => sent.push({ to: room, event, payload }),
      }),
    },
    sent,
    joined,
  }
  handlers(sock)
  return sock
}

const WRITER = {
  ok: true,
  name: 'FILE-1',
  write: true,
  who: { user: 'writer@example.test', full_name: 'Writer One' },
}
const READER = { ...WRITER, write: false, who: { user: 'reader@example.test' } }
const GUEST = {
  ok: true,
  name: 'FILE-1',
  write: true,
  guest: true,
  who: { user: 'link:LINK-1', full_name: 'Consultant' },
}

const ack = (sock, kind, name) =>
  new Promise((done) => sock.fire('oneapp_join', kind, name, done))

describe('the relay lets somebody in', () => {
  it('names the room itself, from what the server said', async () => {
    const sock = fakeSocket({ admit: WRITER })
    // The client asked for a file called `whatever`; the server answered
    // `FILE-1`, and the room is built from the answer.
    const seat = await ack(sock, 'file', 'whatever')
    expect(seat).toMatchObject({ ok: true, room: 'oneapp:file/FILE-1', write: true })
    expect([...sock.joined]).toEqual(['oneapp:file/FILE-1'])
  })

  it('refuses a kind that is not on the list', async () => {
    const sock = fakeSocket({ admit: WRITER })
    // Without this a client could join `oneapp:Sales Invoice/ACC-SINV-0001`
    // and be relayed every message anyone sent about it.
    expect(await ack(sock, 'DocType', 'User')).toEqual({ ok: false })
    expect([...sock.joined]).toEqual([])
  })

  it('refuses when the framework says no', async () => {
    const sock = fakeSocket({ admit: { ok: false } })
    expect(await ack(sock, 'file', 'FILE-1')).toEqual({ ok: false })
  })

  it('hands the link from the handshake to the framework', async () => {
    const sock = fakeSocket({ admit: WRITER, link: 'sekrit' })
    await ack(sock, 'file', 'FILE-1')
    // The relay never decides what a link is worth. It carries it and
    // believes the answer.
    expect(sock.asked[0].args).toEqual({ kind: 'file', name: 'FILE-1', link: 'sekrit' })
  })

  it('makes two strangers on one link two people', async () => {
    // Python cannot tell them apart — same session, same link — and this
    // can, because a socket is a connection. Without it a room with two
    // guests in it shows one face and one cursor.
    const one = fakeSocket({ admit: GUEST, link: 'sekrit', id: 'sock-a' })
    const two = fakeSocket({ admit: GUEST, link: 'sekrit', id: 'sock-b' })
    const first = await ack(one, 'file', 'FILE-1')
    const second = await ack(two, 'file', 'FILE-1')

    expect(first.who.user).not.toBe(second.who.user)
    expect(first.who.user.startsWith('link:LINK-1')).toBe(true)
    expect(first.guest).toBe(true)
  })

  it('leaves a signed-in person with two tabs as one face', async () => {
    const one = fakeSocket({ admit: WRITER, id: 'sock-a' })
    const two = fakeSocket({ admit: WRITER, id: 'sock-b' })
    const first = await ack(one, 'file', 'FILE-1')
    const second = await ack(two, 'file', 'FILE-1')

    expect(first.who.user).toBe(second.who.user)
    expect(first.guest).toBe(false)
  })
})

describe('the relay decides who may speak', () => {
  let sock
  beforeEach(() => { sock = null })

  it('relays a writer to the rest of the room, never back to the sender', async () => {
    sock = fakeSocket({ admit: WRITER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    sock.fire('oneapp_send', 'oneapp:file/FILE-1', 'yjs_update', { a: 1 })

    expect(sock.sent).toEqual([{
      to: 'oneapp:file/FILE-1',
      event: 'oneapp_said',
      payload: {
        room: 'oneapp:file/FILE-1',
        event: 'yjs_update',
        from: 'writer@example.test',
        payload: { a: 1 },
      },
    }])
  })

  it('drops a reader trying to write', async () => {
    sock = fakeSocket({ admit: READER })
    const seat = await ack(sock, 'file', 'FILE-1')
    expect(seat.write).toBe(false)
    sock.sent.length = 0

    sock.fire('oneapp_send', 'oneapp:file/FILE-1', 'yjs_update', { a: 1 })
    expect(sock.sent).toEqual([])
  })

  it('lets a reader ask for the file, which is the one thing they may say', async () => {
    sock = fakeSocket({ admit: READER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    sock.fire('oneapp_ask', 'oneapp:file/FILE-1')
    expect(sock.sent).toEqual([{
      to: 'oneapp:file/FILE-1',
      event: 'oneapp_asked',
      payload: { room: 'oneapp:file/FILE-1', from: 'reader@example.test' },
    }])
  })

  it('will not carry an ask into a room this socket never joined', async () => {
    sock = fakeSocket({ admit: READER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    sock.fire('oneapp_ask', 'oneapp:file/SOMEBODY-ELSES')
    expect(sock.sent).toEqual([])
  })

  it('drops a message into a room this socket never joined', async () => {
    sock = fakeSocket({ admit: WRITER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    sock.fire('oneapp_send', 'oneapp:file/SOMEBODY-ELSES', 'yjs_update', { a: 1 })
    expect(sock.sent).toEqual([])
  })

  it('drops a message too big to be one', async () => {
    sock = fakeSocket({ admit: WRITER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    sock.fire('oneapp_send', 'oneapp:file/FILE-1', 'yjs_update', { big: 'x'.repeat(600 * 1024) })
    expect(sock.sent).toEqual([])
  })

  it('stops a socket that will not stop talking', async () => {
    sock = fakeSocket({ admit: WRITER })
    await ack(sock, 'file', 'FILE-1')
    sock.sent.length = 0

    for (let i = 0; i < 400; i += 1) {
      sock.fire('oneapp_send', 'oneapp:file/FILE-1', 'yjs_update', { i })
    }
    // The ceiling is on abuse, not on typing: a fast typist is nowhere near
    // it, and what matters here is only that it exists.
    expect(sock.sent.length).toBeGreaterThan(100)
    expect(sock.sent.length).toBeLessThan(400)
  })
})

describe('leaving', () => {
  it('leaves the room and stops relaying for it', async () => {
    const sock = fakeSocket({ admit: WRITER })
    await ack(sock, 'file', 'FILE-1')

    sock.fire('oneapp_leave', 'oneapp:file/FILE-1')
    expect([...sock.joined]).toEqual([])

    sock.sent.length = 0
    sock.fire('oneapp_send', 'oneapp:file/FILE-1', 'yjs_update', { a: 1 })
    expect(sock.sent).toEqual([])
  })
})

/**
 * A room on the socket, for the two editors that have more than one person in
 * them.
 *
 * The framework's realtime client, in `runtime/socket.js`, can subscribe and
 * cannot speak: every message Frappe fans out originates in Python. That is
 * right for `list_update` and wrong for a keystroke — Frappe Sheets routes its
 * Yjs updates through a whitelisted method for exactly this reason and had to
 * coalesce them on a 16ms timer after one paste made a browser answer
 * `ERR_INSUFFICIENT_RESOURCES` at five and a half thousand POSTs.
 *
 * So OneApp ships its own handlers into the socketio process the bench already
 * runs — `apps/oneapp/realtime/handlers.js`, loaded by `frappe/realtime` from
 * every installed app — and this is the browser end of them. A message goes
 * browser → node → browsers. Nothing is posted, nothing reaches a Python
 * worker, and there is no second service to deploy.
 *
 * What a room gives back is deliberately the shape Yjs wants: `publish`, `on`
 * and `off`. The collaboration modules in the sheet and the document are
 * Frappe's, taken whole, and they were written against a `{publish, on, off}`
 * adapter — so they plug into this without knowing it is not the thing they
 * were written for.
 */

import { ref, shallowRef } from 'vue'

import { getSocket } from '@/shared/lib/runtime/socket'

// One set of socket listeners for the whole app, however many rooms are open.
// Registering per room would mean N handlers running on every message and N
// removals to get wrong on teardown.
let wired = false
const open = new Map() // room name → the room object

function wire() {
  if (wired) return
  wired = true
  const sock = getSocket()

  sock.on('oneapp_said', (msg) => {
    const room = open.get(msg?.room)
    if (!room) return
    room._deliver(msg.event, msg.payload, msg.from)
  })

  sock.on('oneapp_here', (msg) => {
    const room = open.get(msg?.room)
    if (!room) return
    room.people.value = msg.people || []
    room._roster()
  })

  // A reconnect is a new socket as far as the relay is concerned: it has no
  // memory of which rooms this browser was in. Re-joining here rather than in
  // each caller is why a peer whose wifi blinked comes back with their cursor
  // rather than as a ghost in everybody else's presence strip.
  sock.on('connect', () => {
    for (const room of open.values()) room._rejoin()
  })
}

/**
 * Ask to be let into a room, and get back the means to talk in it.
 *
 * Resolves to `null` when the server will not have us — a file we may only
 * read is admitted with `write: false`, but a file we may not open at all,
 * or a guest session, comes back as nothing. The caller draws a static
 * editor and never learns why, which is the same refusal `open_link` makes
 * for the same reason.
 */
export async function joinRoom(kind, name) {
  wire()
  const sock = getSocket()

  const seat = await new Promise((resolve) => {
    // If the socket is not up yet the emit is buffered by socket.io and the
    // ack arrives on connect; a socket that never connects leaves this
    // pending, which is the right shape — a room nobody is in has nothing
    // to deliver.
    sock.emit('oneapp_join', kind, name, resolve)
  })
  if (!seat?.ok) return null

  const listeners = new Map() // event → Set<cb>
  const roster = new Set()
  const room = {
    name: seat.room,
    write: !!seat.write,
    who: seat.who,
    // Whether this browser was the only one in the room when it arrived. The
    // document needs it: a Yjs room has to be seeded from the stored HTML by
    // exactly one joiner, and two people opening a document in the same
    // second would otherwise seed it twice and read their own prose back
    // doubled.
    first: !!seat.first,
    people: ref([]),
    // The last thing the relay said about who is here, kept as a shallow ref
    // so a presence strip re-renders on identity rather than on every cursor.
    state: shallowRef(null),

    publish(event, payload) {
      sock.emit('oneapp_send', room.name, event, payload)
    },

    tell(to, event, payload) {
      sock.emit('oneapp_tell', room.name, to, event, payload)
    },

    on(event, cb) {
      if (!listeners.has(event)) listeners.set(event, new Set())
      listeners.get(event).add(cb)
    },

    off(event, cb) {
      listeners.get(event)?.delete(cb)
    },

    /**
     * Called when the roster changes — somebody arrived or left.
     *
     * Separate from `on`, because it is not a message anybody sent: it is the
     * relay's own announcement, and awareness needs it as a handshake. A peer
     * who has just arrived has no idea anybody else is here until the people
     * already in the room say so, and the roster changing is the only moment
     * they could know to.
     */
    onPeople(cb) { roster.add(cb) },
    offPeople(cb) { roster.delete(cb) },

    leave() {
      open.delete(room.name)
      listeners.clear()
      roster.clear()
      sock.emit('oneapp_leave', room.name)
    },

    _roster() {
      for (const cb of roster) cb(room.people.value)
    },

    _deliver(event, payload, from) {
      const bucket = listeners.get(event)
      if (!bucket) return
      for (const cb of bucket) cb(payload, from)
    },

    _rejoin() {
      sock.emit('oneapp_join', kind, name, (again) => {
        if (!again?.ok) return
        // The room name cannot change — it is derived from the file — so the
        // listeners stay wired. What can change is whether we may still
        // write: a share revoked while the tab was asleep must take effect
        // on the way back in.
        room.write = !!again.write
      })
    },
  }

  open.set(room.name, room)
  room.people.value = []
  return room
}

/** Every room this tab is in. Test seam, and the thing `closeSocket` clears. */
export function openRooms() {
  return [...open.keys()]
}

export function leaveAllRooms() {
  for (const room of [...open.values()]) room.leave()
}

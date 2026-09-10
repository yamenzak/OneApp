/**
 * Where everybody's caret is.
 *
 * Awareness is Yjs's name for the volatile half of collaboration: a cursor, a
 * selection, which tab somebody is looking at. It is deliberately *not* in the
 * document — a caret from a session that ended is not something to converge
 * on, it is something to forget — and y-protocols ships the standard one, with
 * its own clock, its own thirty-second expiry and its own wire format.
 *
 * This is that Awareness, bound to a room. Frappe re-implemented the shape
 * rather than take the dependency; we take it, because Tiptap's caret
 * extension for the document editor expects the real thing and two awareness
 * implementations for two editors in one suite is exactly the kind of drift
 * this repository spends its time removing.
 *
 * ## Who a peer is, and who says so
 *
 * An awareness state is written by the client it describes, so anything in it
 * is a claim. The relay knows better: it stamped every message with the user
 * the socket was admitted as. So each incoming frame's client ids are recorded
 * against that user, and `ownerOf` is what a presence strip or a caret label
 * reads. A peer can lie about where its cursor is. It cannot lie about being
 * somebody else.
 */

import * as awarenessProtocol from 'y-protocols/awareness'

import { fromBase64, toBase64 } from '@/shared/lib/live/bytes'

const EVT = 'yjs_awareness'

// Marks an update this client applied rather than made, so the `update`
// handler does not send it straight back out.
const FROM_ROOM = Symbol('room')

/**
 * @param {object} opts
 * @param {import('yjs').Doc} opts.doc  the room's document; awareness borrows
 *                                      its client id, which is what ties a
 *                                      caret to the edits beside it
 * @param {object} opts.room            what `joinRoom` returned
 */
export function createAwareness({ doc, room } = {}) {
  if (!doc || !room) throw new Error('createAwareness: doc and room are required')

  const awareness = new awarenessProtocol.Awareness(doc)
  const owners = new Map() // Yjs client id → the user the relay admitted

  // Set for the duration of one `applyAwarenessUpdate`, which is synchronous,
  // so the `update` handler it triggers knows who the frame came from.
  let arriving = null

  function send(clients) {
    if (!clients.length) return
    room.publish(EVT, { u: toBase64(awarenessProtocol.encodeAwarenessUpdate(awareness, clients)) })
  }

  const onLocal = ({ added, updated, removed }, origin) => {
    if (arriving !== null) {
      for (const id of [...added, ...updated]) {
        owners.set(id, arriving)
        stamp(id, arriving)
      }
      for (const id of removed) owners.delete(id)
    }
    if (origin === FROM_ROOM) return
    send([...added, ...updated, ...removed])
  }

  /**
   * Overwrite an arriving state's `user` with the relay's answer.
   *
   * A caret in the prose carries a name and a colour, and a caret label is
   * drawn from the state — which the peer wrote. Left alone, anybody in the
   * room could put somebody else's name on their own cursor. So the name and
   * colour come from the roster, keyed on the user the relay admitted the
   * socket as, and whatever the sender claimed is discarded on arrival.
   *
   * This is the same guarantee `ownerOf` gives the grid, made where the
   * document needs it: Tiptap's caret extension renders from `user` and never
   * sees a client id.
   */
  function stamp(clientId, who) {
    const state = awareness.states.get(clientId)
    if (!state) return
    const person = room.people.value.find((one) => one.user === who)
    state.user = {
      id: who,
      name: person?.full_name || who,
      color: person?.colour || '#64748b',
    }
  }

  const onRemote = (payload, who) => {
    if (!payload?.u) return
    arriving = who
    try {
      awarenessProtocol.applyAwarenessUpdate(awareness, fromBase64(payload.u), FROM_ROOM)
    } finally {
      arriving = null
    }
  }

  // Somebody arrived. They have no idea we are here until we say so — the
  // relay tells us the roster changed, and this is the whole handshake.
  const onRoster = () => send([awareness.clientID])

  awareness.on('update', onLocal)
  room.on(EVT, onRemote)
  room.onPeople(onRoster)

  send([awareness.clientID])

  // The Awareness itself, with two of ours on it. Returning a wrapper meant
  // every caller reading `x.awareness.setLocalStateField(…)`, and a wrapper
  // that exists to be unwrapped is not a wrapper.
  awareness.ownerOf = (clientId) => owners.get(clientId) || null
  awareness.leave = () => {
    awareness.off('update', onLocal)
    room.off(EVT, onRemote)
    room.offPeople(onRoster)
    // Say goodbye rather than time out. Thirty seconds of a ghost caret in
    // somebody else's paragraph is thirty seconds of them not typing there.
    awarenessProtocol.removeAwarenessStates(awareness, [awareness.clientID], 'left')
    send([awareness.clientID])
    awareness.destroy()
  }
  return awareness
}

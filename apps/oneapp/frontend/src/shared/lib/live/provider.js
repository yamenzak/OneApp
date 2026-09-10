// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Derived from frappe/sheets, frontend/src/collab/frappe-provider.js, which is
// AGPL-3.0. OneSpace is AGPL-3.0 too and this file stays that way.
//
// What is theirs: the shape. A Y.Doc, local updates coalesced on a short timer
// and published as base64, a state-request on join that any online peer
// answers with a full encode, and an origin tag so an update this client just
// applied does not go back out.
//
// What is ours: the transport underneath it, and it is the half that was
// expensive. Theirs publishes through a whitelisted method — one HTTP POST
// into a Python worker per flush — and their own comment records what that
// cost on a bulk edit: roughly five and a half thousand POSTs and a browser
// out of connection slots. `room.js` publishes into the socketio process the
// bench already runs and Python never sees an update.
//
// Two things that follows. The coalescing window stays, because merging is
// cheaper than sending either way, but it is no longer load-bearing. And the
// state reply is point-to-point (`room.tell`) rather than a broadcast, which
// is what their `to:` field was reaching for and could not have: pushing a
// whole document at every open tab each time somebody arrives is the one
// message here big enough to matter.
//
// One thing is ours outright: the *request* is `room.ask()`, a relay event
// with no payload, rather than a published message. A reader may not publish
// — that is what stops them editing — and a reader who cannot ask is a reader
// who joins an occupied room and is never sent the document.

import * as Y from 'yjs'

import { fromBase64, toBase64 } from '@/shared/lib/live/bytes'

export const REMOTE_ORIGIN = Symbol('remote')

const EVT_UPDATE = 'yjs_update'
const EVT_STATE = 'yjs_state'

/**
 * Keep one Y.Doc in step with everybody else in a room.
 *
 * @param {object} opts
 * @param {import('yjs').Doc} opts.doc
 * @param {object} opts.room            what `joinRoom` returned
 * @param {number} [opts.flushIntervalMs] one frame; invisible to a typist
 * @param {number} [opts.maxQueuedUpdates]
 */
export function createProvider({
  doc,
  room,
  // Called once, the first time somebody in the room answers our
  // state-request. A joiner that is not the first has a Y.Doc that only
  // becomes true at that moment, and whatever it loaded from the server
  // before then may be a version behind — a cell somebody deleted while this
  // tab was opening is still in the local engine, and would be written back
  // by the next save. Only the caller can reconcile that, so it is told.
  onSynced,
  flushIntervalMs = 16,
  maxQueuedUpdates = 256,
  _setTimeout = setTimeout,
  _clearTimeout = clearTimeout,
} = {}) {
  if (!doc || !room) throw new Error('createProvider: doc and room are required')

  // Per tab, not per person: somebody with the same file open twice is two
  // peers as far as convergence is concerned, and an update must not be
  // ignored by the other tab just because it came from the same account.
  const tag = `tab-${Math.random().toString(36).slice(2, 10)}`
  let stopped = false
  let pending = []
  let timer = null

  function flush() {
    if (timer) { _clearTimeout(timer); timer = null }
    if (stopped || !pending.length) return
    const merged = pending.length === 1 ? pending[0] : Y.mergeUpdates(pending)
    pending = []
    room.publish(EVT_UPDATE, { from: tag, update: toBase64(merged) })
  }

  const onLocal = (update, origin) => {
    if (stopped || origin === REMOTE_ORIGIN) return
    pending.push(update)
    if (pending.length >= maxQueuedUpdates) { flush(); return }
    if (!timer) timer = _setTimeout(flush, flushIntervalMs)
  }

  const onUpdate = (payload) => {
    if (stopped || !payload || payload.from === tag) return
    Y.applyUpdate(doc, fromBase64(payload.update), REMOTE_ORIGIN)
  }

  const onAsked = (fromUser) => {
    if (stopped || !fromUser) return
    // Anything still queued is already in the doc, so send it as part of the
    // state rather than twice — once here and again on the deferred flush.
    flush()
    room.tell(fromUser, EVT_STATE, {
      from: tag, update: toBase64(Y.encodeStateAsUpdate(doc)),
    })
  }

  let synced = false
  const onState = (payload) => {
    if (stopped || !payload || payload.from === tag) return
    Y.applyUpdate(doc, fromBase64(payload.update), REMOTE_ORIGIN)
    if (synced) return
    synced = true
    onSynced?.()
  }

  doc.on('update', onLocal)
  room.on(EVT_UPDATE, onUpdate)
  room.onAsk(onAsked)
  room.on(EVT_STATE, onState)

  // Announce ourselves, so whoever is already here replays us what they have.
  // `ask` rather than a published message, because a reader may not publish
  // and this is the one thing a reader most needs to do — see `oneapp_ask`.
  room.ask()

  function destroy() {
    // Before the guard, so the last burst of typing lands at the other people
    // in the room rather than dying with the tab that was closed.
    flush()
    stopped = true
    if (timer) { _clearTimeout(timer); timer = null }
    doc.off('update', onLocal)
    room.off(EVT_UPDATE, onUpdate)
    room.offAsk(onAsked)
    room.off(EVT_STATE, onState)
  }

  return { destroy, tag, flush }
}

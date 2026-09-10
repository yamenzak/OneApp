/**
 * Cell notes, converging.
 *
 * Ours, not Frappe's — their Yjs work binds cells and leaves the comments map
 * in `ydoc.js` declared and unused. The engine underneath is theirs
 * (`lib/engine/comments.js`): threaded, resolvable, `@`-mentionable notes per
 * cell, already stored in the workbook's payload and already drawn. What was
 * missing is that a note somebody adds in one browser stays there until the
 * next save and reload.
 *
 * ## Why a thread is a Y.Array and not a value
 *
 * The obvious binding is the one `cells-binding.js` uses: put the whole thread
 * object under the cell id and let Yjs resolve. That is right for a cell,
 * where the loser of a concurrent write typed a value somebody immediately
 * overwrote, and wrong for a thread, where the loser wrote a *reply* that
 * simply vanishes. So the replies are a `Y.Array` and a reply is an insert:
 * two people answering the same note at the same moment both get answered.
 *
 * Everything else about a thread — whether it is resolved — is a value, and
 * last writer wins is the right answer there.
 *
 * Shape:
 *
 *   comments : Y.Map< sheetName, Y.Map< cellId, Y.Map{
 *                resolved : boolean,
 *                thread   : Y.Array< reply > } > >
 */

import * as Y from 'yjs'

import { ROOT } from '@/modules/onesheet/lib/collab/ydoc.js'

const LOCAL = Symbol('local-comment')

/**
 * @param {object} opts
 * @param {import('yjs').Doc} opts.doc
 * @param {object} opts.comments      the engine from `createCommentsEngine()`
 * @param {() => string} opts.current the sub-sheet the person is looking at
 * @param {() => void} [opts.onRemote] repaint the badge and the open panel
 */
export function bindComments({ doc, comments, current, onRemote } = {}) {
  if (!doc || !comments) throw new Error('bindComments: doc and comments are required')

  const root = doc.getMap(ROOT.COMMENTS)
  const watching = new Map() // sheetName → unobserve

  const original = {
    addReply: comments.addReply,
    removeReply: comments.removeReply,
    resolve: comments.resolve,
    clear: comments.clear,
    setThread: comments.setThread,
  }

  function tab(name) {
    let found = root.get(name)
    if (!(found instanceof Y.Map)) {
      found = new Y.Map()
      root.set(name, found)
    }
    return found
  }

  function cell(name, id) {
    const held = tab(name)
    let found = held.get(id)
    if (!(found instanceof Y.Map)) {
      found = new Y.Map()
      found.set('resolved', false)
      found.set('thread', new Y.Array())
      held.set(id, found)
    }
    return found
  }

  // ── engine → doc ────────────────────────────────────────────────────────

  comments.addReply = function addReply(id, reply, sheetName) {
    const name = sheetName || current()
    original.addReply.call(comments, id, reply, name)
    doc.transact(() => {
      // Read back what the engine actually stored rather than echoing the
      // argument: it fills in the timestamp and the defaults, and a reply
      // that reads differently on two screens is a reply people argue about.
      const thread = comments.getThread(id, name)
      const last = thread?.thread?.[thread.thread.length - 1]
      if (last) cell(name, id).get('thread').push([{ ...last }])
    }, LOCAL)
  }

  comments.removeReply = function removeReply(id, index, sheetName) {
    const name = sheetName || current()
    original.removeReply.call(comments, id, index, name)
    doc.transact(() => {
      const held = tab(name).get(id)
      const thread = held instanceof Y.Map ? held.get('thread') : null
      if (thread instanceof Y.Array && index < thread.length) thread.delete(index, 1)
      // The engine drops an empty thread; keep the two in step.
      if (!comments.getThread(id, name)) tab(name).delete(id)
    }, LOCAL)
  }

  comments.resolve = function resolveThread(id, resolved, sheetName) {
    const name = sheetName || current()
    original.resolve.call(comments, id, resolved, name)
    doc.transact(() => {
      const held = tab(name).get(id)
      if (held instanceof Y.Map) held.set('resolved', !!resolved)
    }, LOCAL)
  }

  comments.clear = function clearThread(id, sheetName) {
    const name = sheetName || current()
    original.clear.call(comments, id, name)
    doc.transact(() => tab(name).delete(id), LOCAL)
  }

  /**
   * The wholesale setter, which is what undo and the row/column shifts go
   * through. Replacing the Y.Array rather than diffing it: a shift moves
   * every note below the insertion point, and the alternative is working out
   * which of them moved.
   */
  comments.setThread = function setThread(id, value, sheetName) {
    const name = sheetName || current()
    original.setThread.call(comments, id, value, name)
    doc.transact(() => {
      if (!value) { tab(name).delete(id); return }
      const held = cell(name, id)
      held.set('resolved', !!value.resolved)
      const thread = held.get('thread')
      thread.delete(0, thread.length)
      thread.push((value.thread || []).map((one) => ({ ...one })))
    }, LOCAL)
  }

  // ── doc → engine ────────────────────────────────────────────────────────

  function pull(name, id) {
    const held = tab(name).get(id)
    if (!(held instanceof Y.Map)) {
      original.setThread.call(comments, id, null, name)
      return
    }
    const thread = held.get('thread')
    original.setThread.call(comments, id, {
      resolved: !!held.get('resolved'),
      thread: thread instanceof Y.Array ? thread.toArray().map((one) => ({ ...one })) : [],
    }, name)
  }

  function watch(name, held) {
    unwatch(name)
    const handler = (events, transaction) => {
      if (transaction.origin === LOCAL) return
      const touched = new Set()
      for (const event of events) {
        // The path from the sheet's map: [] on the map itself (a cell added
        // or removed), [cellId] on one cell, [cellId, 'thread'] on a reply.
        if (event.path.length === 0) {
          event.changes.keys.forEach((_change, id) => touched.add(id))
        } else {
          touched.add(event.path[0])
        }
      }
      for (const id of touched) pull(name, id)
      if (touched.size) onRemote?.()
    }
    held.observeDeep(handler)
    watching.set(name, () => held.unobserveDeep(handler))
  }

  function unwatch(name) {
    const off = watching.get(name)
    if (off) { off(); watching.delete(name) }
  }

  for (const [name, held] of root.entries()) {
    if (held instanceof Y.Map) watch(name, held)
  }

  const onRoot = (event) => {
    event.changes.keys.forEach((change, name) => {
      if (change.action === 'delete') { unwatch(name); return }
      const held = root.get(name)
      if (!(held instanceof Y.Map)) return
      watch(name, held)
      if (event.transaction.origin === LOCAL) return
      for (const id of held.keys()) pull(name, id)
      onRemote?.()
    })
  }
  root.observe(onRoot)

  /** Seed the room from this client's engine. Only the first person in. */
  function hydrate() {
    const all = comments.snapshot()
    doc.transact(() => {
      for (const [name, cells] of Object.entries(all || {})) {
        for (const [id, value] of Object.entries(cells || {})) {
          if (!value) continue
          const held = cell(name, id)
          held.set('resolved', !!value.resolved)
          held.get('thread').push((value.thread || []).map((one) => ({ ...one })))
        }
      }
    }, LOCAL)
  }

  function dispose() {
    Object.assign(comments, original)
    root.unobserve(onRoot)
    for (const off of watching.values()) off()
    watching.clear()
  }

  return { hydrate, dispose }
}

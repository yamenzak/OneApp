// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Derived from frappe/sheets (3f9e37b5776f),
// frontend/src/pages/SheetEditor/useCollaboration.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see lib/VENDORED.md.

/**
 * Two people in one workbook.
 *
 * This file used to answer empty, and the comment where it did said Yjs needs
 * a second Node process. It does not: Frappe's socketio loads
 * `apps/oneapp/realtime/handlers.js` from this app, so the relay runs in the
 * process the bench already runs. `docs/COLLABORATION.md` is the argument;
 * what is left here is the wiring.
 *
 * The shape is Frappe's and worth keeping. A Y.Doc per workbook with the raw
 * cell values in it, `bindCells` patching the engine's `setCell` in both
 * directions, and awareness carrying the carets. The engine stays the source
 * of truth for everything computed — formulas, the dependency graph, what a
 * cell displays — so nothing about the formula engine is ever on the wire and
 * a peer who receives a rate recomputes the total themselves.
 *
 * Two departures, both deliberate.
 *
 * **Identity comes from the relay, not from awareness.** Theirs puts the
 * peer's name and avatar in awareness, which means a client asserts who it is
 * and everybody draws it. Here the roster is the server's answer to `admit`,
 * and awareness carries only where the caret is. A peer can lie about that and
 * about nothing else.
 *
 * **There is no Hocuspocus path and no feature flag.** Theirs carries both
 * transports and a `collab_v2` switch to pick between them; we have one
 * transport and it is always the same one.
 *
 * The outward API is unchanged from the file this replaces, so `index.vue`
 * needed no edit: `broadcastCellChange` and `broadcastBatchChange` are no-ops
 * because the patched `setCell` already published, and `drainLocalTouches` is
 * what lets undo revert this client's cells and leave a colleague's alone.
 */

import { ref, watch, onUnmounted } from 'vue'

import { joinRoom } from '@/shared/lib/live/room'
import { createProvider } from '@/shared/lib/live/provider'
import { createAwareness } from '@/shared/lib/live/awareness'
import { createYDoc, hydrateYDoc, ROOT } from '@/modules/onesheet/lib/collab/ydoc.js'
import { bindCells } from '@/modules/onesheet/lib/collab/cells-binding.js'

// A drag-selection across thirty cells is one intention, not thirty. 60ms is
// about a frame: the first move goes at once, the resting position always
// goes, and the smear between them does not.
const CURSOR_MS = 60

function throttle(fn, wait) {
  let last = 0
  let timer = null
  let pending = null
  function flush() {
    last = Date.now()
    timer = null
    if (pending) { fn(...pending); pending = null }
  }
  return function throttled(...args) {
    const remaining = wait - (Date.now() - last)
    pending = args
    if (remaining <= 0) {
      if (timer) { clearTimeout(timer); timer = null }
      flush()
    } else if (!timer) {
      timer = setTimeout(flush, remaining)
    }
  }
}

// What a cursor is labelled with. A first name reads at a glance and does not
// say the same thing as the initials on the avatar beside it.
function firstName(full, initials) {
  return String(full || '').trim().split(/\s+/)[0] || initials || '?'
}

export function useCollaboration({
  sheetId,
  currentSheet,
  getSheet,
  repopulateGrid,
  canCollaborate = { value: true },
  // False until `get_sheet` has come back and the engines hold the workbook.
  // Joining before that is the one way to lose a whole file: the first person
  // in the room seeds it from what they have, and what an editor has three
  // hundred milliseconds after mount is an empty grid.
  ready = { value: true },
  _joinRoom = joinRoom,
  _watch = watch,
  _onUnmounted = onUnmounted,
} = {}) {
  const presentUsers = ref([])
  const remoteCursors = ref(new Map())

  let room = null
  let doc = null
  let provider = null
  let awareness = null
  let binding = null
  let stopPeople = null
  // Bumped on every start, so a join that resolves after the workbook has
  // moved on does not wire a room for a sheet nobody is looking at.
  let generation = 0

  function broadcastCellChange() {
    // The patched `sheet.setCell` from `bindCells` already put this in the
    // Y.Map and the provider already sent it. Kept so `index.vue`'s call
    // sites do not have to know that.
  }

  function broadcastBatchChange() {}

  function publishCursor(row, col, subSheet, range) {
    awareness?.setLocalStateField('cursor', { row, col, range, subSheet })
    awareness?.setLocalStateField('subSheet', subSheet)
  }
  const publishCursorSoon = throttle(publishCursor, CURSOR_MS)

  function broadcastCursor(row, col, subSheet, range = null) {
    publishCursorSoon(row, col, subSheet, range)
  }

  /**
   * Fold the two halves together: who is here, from the relay, and where each
   * of them is, from awareness.
   *
   * Somebody with the file open in two tabs is one face and one cursor — the
   * tab that moved last — which is why this is keyed by person rather than by
   * connection.
   */
  function recompute() {
    if (!room) return
    // Keyed by person, not by connection: somebody with the file open twice
    // is one face and one cursor, whichever tab moved last. `ownerOf` is the
    // relay's answer to who a client id belongs to — the state itself is
    // written by that client and cannot be trusted to say.
    const cursorFor = new Map()
    if (awareness) {
      for (const [id, state] of awareness.getStates()) {
        const who = awareness.ownerOf(id)
        if (!who || who === room.who.user) continue
        cursorFor.set(who, state)
      }
    }

    const users = []
    const cursors = new Map()
    for (const who of room.people.value) {
      if (who.user === room.who.user) continue
      const state = cursorFor.get(who.user)
      users.push({
        user: who.user,
        full_name: who.full_name,
        first_name: firstName(who.full_name, who.initials),
        initials: who.initials,
        user_image: who.image,
        color: who.colour,
        sub_sheet: state?.subSheet || null,
      })
      const at = state?.cursor
      if (!at) continue
      cursors.set(who.user, {
        row: at.row,
        col: at.col,
        range: at.range || { r0: at.row, c0: at.col, r1: at.row, c1: at.col },
        subSheet: at.subSheet,
        color: who.colour,
        fullName: who.full_name,
        firstName: firstName(who.full_name, who.initials),
        initials: who.initials,
      })
    }
    presentUsers.value = users
    remoteCursors.value = cursors
  }

  async function start(name) {
    stop()
    const mine = (generation += 1)

    const seat = await _joinRoom('file', name)
    // Refused — a guest, or a file this person may only reach through a link
    // — or the workbook moved on while we were asking. Either way the editor
    // draws the static workbook it already loaded and says nothing.
    if (!seat || mine !== generation) { seat?.leave(); return }
    room = seat

    doc = createYDoc()
    binding = bindCells({
      doc,
      sheet: getSheet(),
      onRemoteSheetChange(changed) {
        // Frappe's condition, and it reads backwards until you know why. A
        // write to the tab you are on paints itself: the engine's own
        // `onCellChanged` is bound to the active grid, and its dependency
        // graph repaints whatever on that tab depended on the cell. A write
        // to *another* tab paints nothing at all — and a formula here that
        // reads across to it is now stale on screen with no way to know.
        // So the repaint is for the case that looks like it needs one least.
        if (changed !== currentSheet.value) repopulateGrid()
      },
    })

    // Exactly one client seeds the room, and the relay says which: the one
    // that found it empty. Frappe lets every client hydrate its own doc and
    // relies on the merge, which converges on identical content and does not
    // converge on a *deletion* — a cell one person removed and another still
    // has is a coin flip between two concurrent writes. Seeding once removes
    // the concurrency rather than resolving it.
    if (seat.first) hydrateYDoc(doc, { sheet: getSheet().snapshot() })

    provider = createProvider({
      doc,
      room,
      // The other half of the same problem. A late joiner loaded the workbook
      // from the server, which may be a save behind what the room has been
      // doing; the room's state adds and changes cells but cannot remove one
      // this tab loaded and the room no longer has. Left alone, the next
      // autosave from this tab writes it back and the deletion is undone for
      // everybody. So once the room has answered, the cells are the room's.
      onSynced: () => takeRoomCells(mine),
    })
    awareness = createAwareness({ doc, room })
    awareness.setLocalStateField('subSheet', currentSheet.value)
    awareness.on('change', recompute)
    stopPeople = _watch(room.people, recompute, { deep: true })
    recompute()
  }

  /**
   * Replace this client's cells with the room's, everything else untouched.
   *
   * Cells only, and deliberately: the Y.Doc carries raw values and nothing
   * else, so formats, merges, validation and protection stay as they were
   * loaded — they came out of the same saved payload and there is nothing
   * better to replace them with. `_origSetCell` through the binding rather
   * than `sheet.restore`, so the dependency graph is rebuilt cell by cell and
   * a formula that now reads a different number recomputes.
   */
  function takeRoomCells(mine) {
    if (mine !== generation || !doc || !binding) return
    const sheet = getSheet()
    const rooms = doc.getMap(ROOT.CELLS)
    for (const [tab, cells] of rooms.entries()) {
      const had = new Set(Object.keys(sheet.snapshot().sheets[tab] || {}))
      for (const [id, value] of cells.entries()) {
        binding.applyRemote(id, value, tab)
        had.delete(id)
      }
      // What this tab had and the room does not: the deletions it missed.
      for (const id of had) binding.applyRemote(id, '', tab)
    }
    repopulateGrid()
  }

  function stop() {
    generation += 1
    stopPeople?.()
    binding?.dispose()
    awareness?.off('change', recompute)
    awareness?.leave()
    provider?.destroy()
    room?.leave()
    doc?.destroy()
    stopPeople = binding = awareness = provider = room = doc = null
    presentUsers.value = []
    remoteCursors.value = new Map()
  }

  _watch([sheetId, ready], ([name, loaded]) => {
    if (name && name !== 'new' && loaded && canCollaborate.value) start(name)
    else stop()
  }, { immediate: true })

  // So a peer's tab dot follows somebody switching tabs, without waiting for
  // them to move the caret.
  _watch(currentSheet, (name) => {
    awareness?.setLocalStateField('subSheet', name)
  })

  _onUnmounted(stop)

  function drainLocalTouches() {
    return binding?.drainLocalTouches?.() || new Set()
  }

  return {
    presentUsers,
    remoteCursors,
    broadcastCellChange,
    broadcastBatchChange,
    broadcastCursor,
    drainLocalTouches,
  }
}

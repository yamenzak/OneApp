/**
 * Two people in one document.
 *
 * The grid could take Frappe's Yjs layer whole because a workbook is cells in
 * a map and a cell is a value. Prose is not: two people typing in the same
 * paragraph is the case a CRDT exists for, and rebuilding that would be
 * rebuilding ProseMirror's. So this is Tiptap's own collaboration extension
 * over the transport from `shared/lib/live/` — the same room, the same
 * provider, the same awareness the sheet uses.
 *
 * **The HTML stays the stored form.** `docs/WRITER.md` §3 declined Frappe
 * Writer's model partly because it stores a base64 CRDT as the document, and
 * that objection stands: a document has to be a column anybody can read, a
 * version has to be a snapshot rather than a replay, and an export has to read
 * the same bytes the editor does. So the Y.Doc lives only as long as somebody
 * has the file open. It is seeded from the stored content by whichever browser
 * the relay says found the room empty, everybody saves the ordinary debounced
 * save, and when the last person leaves there is nothing left of it.
 *
 * What that costs is honest and small: two people editing while *nobody* is
 * connected to the room cannot happen, because being in the room is what
 * connecting means. What it buys is that nothing about the storage changed.
 */

import { shallowRef, ref } from 'vue'

import { getSchema } from '@tiptap/core'
import { prosemirrorJSONToYDoc } from 'y-prosemirror'
import * as Y from 'yjs'

import { joinRoom } from '@/shared/lib/live/room'
import { createProvider } from '@/shared/lib/live/provider'
import { createAwareness } from '@/shared/lib/live/awareness'

// Tiptap's own default. Named here because the seed has to build the same
// fragment the extension will bind to, and a mismatch is a document that
// syncs an empty paragraph over the one you were reading.
const FIELD = 'default'

/**
 * @param {object} opts
 * @param {string} opts.name      the File this document is
 * @param {object|null} opts.initial  the stored ProseMirror JSON, for the seed
 * @param {(collab: {document: import('yjs').Doc, awareness: object}|null) => Array} opts.build
 *        the extension list, with and without collaboration. Called with
 *        `null` once for the schema the seed needs.
 */
export function useLiveDocument({ name, initial, build }) {
  // False until we know whether this document is live, and the editor must
  // not mount before it: frappe-ui's `useEditor` decides collaboration mode
  // from the extension list *at construction*, and an editor built without
  // the extension would set its own content and then have the room's merged
  // on top of it — the same paragraph twice.
  const decided = ref(false)
  const room = shallowRef(null)
  const extensions = shallowRef(build(null))
  const people = ref([])

  let doc = null
  let provider = null
  let awareness = null

  async function start() {
    let seat = null
    try {
      seat = await joinRoom('file', name)
    } catch {
      seat = null
    }
    // Refused, or the socket never came up. A document that cannot join a
    // room is the document this product had until now, and it says nothing
    // about it: one person editing one file is not a degraded experience.
    if (!seat) { decided.value = true; return }

    room.value = seat
    people.value = seat.people.value
    seat.onPeople((who) => { people.value = who })

    doc = seat.first && initial
      ? prosemirrorJSONToYDoc(getSchema(build(null)), initial, FIELD)
      : new Y.Doc()

    provider = createProvider({ doc, room: seat })
    awareness = createAwareness({ doc, room: seat })
    // Our own caret's label. Everybody else's is stamped from the roster when
    // it arrives — see `shared/lib/live/awareness.js` — so this is the one
    // place the claim and the truth are the same thing by construction.
    awareness.setLocalStateField('user', {
      id: seat.who.user,
      name: seat.who.full_name,
      color: seat.who.colour,
    })

    extensions.value = build({ document: doc, awareness })
    decided.value = true
  }

  function stop() {
    awareness?.leave()
    provider?.destroy()
    room.value?.leave()
    doc?.destroy()
    awareness = provider = doc = null
    room.value = null
    people.value = []
  }

  start()

  return { decided, room, extensions, people, stop }
}

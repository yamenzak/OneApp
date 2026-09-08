/**
 * Two people in one sheet at once — not built, and this is the seam where it
 * would go.
 *
 * Frappe does it with Yjs: a CRDT document per sheet, synchronised through
 * `@hocuspocus/server`, which is a *separate Node process* beside the Frappe
 * one with Redis behind it for fan-out. That is a second runtime to deploy,
 * watch and pay for on every tenant, and `docs/SHEETS.md` Stage 7 is the
 * argument for not taking it on yet.
 *
 * Everything here answers empty. `presentUsers` stays a list of nobody, the
 * broadcasts go nowhere, and `drainLocalTouches` returns an empty set — which
 * is exactly what the editor's undo expects when there is no binding, so undo
 * falls back to restoring its own snapshot rather than reverting only the cells
 * this client wrote.
 *
 * Keep the shape. Replacing this file with the real one should not need a line
 * changed in `index.vue`.
 */

import { ref } from 'vue'

const NOBODY = []

export function useCollaboration() {
  return {
    presentUsers: ref(NOBODY),
    remoteCursors: ref(new Map()),
    broadcastCellChange: () => {},
    broadcastBatchChange: () => {},
    broadcastCursor: () => {},
    drainLocalTouches: () => new Set(),
  }
}

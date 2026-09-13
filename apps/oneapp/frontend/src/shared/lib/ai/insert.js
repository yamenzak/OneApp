/**
 * Where an answer can be put, when the thing you are looking at can take one.
 *
 * The assistant answers in the chat and cannot type into a document — that is
 * the split `lib/ai/openers.js` describes and it is the right one: a transform
 * belongs where the selection is, a question belongs in the widget. But it
 * leaves one obvious thing undone. Ask it "draft a to-whom-it-may-concern for
 * these employees" beside the document you want it in, and the answer arrives
 * as something to select and copy.
 *
 * So a page may offer itself as a destination. The widget draws **Insert** on
 * an answer only while something is offering, and pressing it hands the text
 * over — the page decides what that means, because only the page knows where
 * the cursor is, what an undo step should contain, and how to mark the result
 * as written by a model.
 *
 * A registry rather than a prop for the reason `lib/ai/context.js` is one: the
 * widget is mounted in the shell and the document is in the router view, so
 * neither is the other's parent and there is nothing to pass it down.
 *
 * One at a time, and the last to mount wins. Two surfaces claiming to be where
 * an answer goes is a question with no answer, and the case that would cause
 * it — a document open in the Drive's pane — is one where the document is the
 * right answer and mounts second anyway.
 */

import { getCurrentScope, onScopeDispose, shallowRef } from 'vue'

const offered = shallowRef(null)

/**
 * Offer this component as somewhere an answer can go, while it is mounted.
 *
 * `describe` returns `{ label, insert }` or nothing — nothing because the
 * offer is conditional in practice: a document opened through a share link, or
 * one somebody may only read, is a document with nowhere to put anything, and
 * a button that refuses is worse than a button that is not there.
 */
export function useAiInsert(describe) {
  const mine = { describe }
  offered.value = mine
  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (offered.value === mine) offered.value = null
    })
  }
}

/**
 * What is on offer now, or null.
 *
 * Called inside a `computed` this tracks whatever the page's own `describe`
 * reads, so a document that finishes loading — or one that becomes read-only
 * because somebody locked it — changes the button without telling anybody.
 */
export function insertTarget() {
  return offered.value?.describe?.() || null
}

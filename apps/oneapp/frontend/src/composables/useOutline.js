/**
 * The headings of the document on screen, and how to jump to one.
 *
 * Derived from the editor's own document on every transaction rather than from
 * a table-of-contents extension. frappe-ui ships one, and it inserts a ToC
 * *into* the page — which is a block somebody puts in a report, not a rail that
 * follows the cursor. Reading the headings is a walk over the doc, which is
 * cheap enough to do on every keystroke and always describes the text that is
 * actually there.
 *
 * A composable rather than something `Outline.vue` owns, because a phone has no
 * room for a rail and gets the same list as a dropdown in the header. Two
 * copies of "which headings are there" is the pair that drifts.
 */

import { computed, ref } from 'vue'

export function useOutline(editor, revision) {
  const active = ref('')

  const headings = computed(() => {
    // Read so this re-runs when the host says the document moved: ProseMirror
    // mutates its own state in place, so the editor ref alone is not reactive.
    void revision.value

    const doc = editor.value?.state?.doc
    if (!doc) return []

    const found = []
    doc.descendants((node, pos) => {
      if (node.type.name !== 'heading') return
      const text = node.textContent.trim()
      if (text) found.push({ id: node.attrs.id || `h-${pos}`, pos, level: node.attrs.level, text })
    })
    return found
  })

  /** Whether it is worth drawing at all: a list of one says nothing new. */
  const worthShowing = computed(() => headings.value.length > 1)

  function go(one) {
    active.value = one.id
    // Through the editor rather than `getElementById`: a heading has an id only
    // where frappe-ui's HeadingIds extension gave it one, and the position is
    // what the editor itself scrolls to.
    editor.value?.chain().focus().setTextSelection(one.pos + 1).scrollIntoView().run()
  }

  return { headings, worthShowing, active, go }
}

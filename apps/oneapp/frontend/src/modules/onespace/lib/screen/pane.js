/**
 * How wide the record pane is.
 *
 * Module-level rather than inside `ObjectPane`, because two things have to
 * agree about it now: the pane itself, and the block of the top bar that sits
 * over the pane and carries its trail. A header that is not exactly as wide as
 * the panel under it is a header belonging to something else.
 *
 * The value is written by the pane's own `Resizer`, which is also what
 * remembers it per browser — this is where it lives, not where it persists.
 */
import { ref } from 'vue'

/** Narrow enough that a form is still readable, and no narrower: below this
 *  the labels wrap and the pane is a column of hyphens. */
export const MIN = 360
export const DEFAULT = 480

const width = ref(DEFAULT)

export function useObjectPane() {
  return { width }
}

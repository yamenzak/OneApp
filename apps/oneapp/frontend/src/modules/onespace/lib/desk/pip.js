/**
 * The list you came from, in a window, while you read one of its rows.
 *
 * `docs/DESKTOP.md`'s second decision: a record stops being a pane beside its
 * list and becomes a page — but the pane was doing a real job, and it was not
 * "two things side by side". It was **mark this one done, glance at the next,
 * come back**, which is getting back to the list without losing it. The
 * breadcrumb already names the place; this is what happens when you press it.
 *
 * **There is one, and it is the list that is already there.** That is the whole
 * design and it is worth saying plainly, because the obvious build is a second
 * screen host inside the window that re-resolves the screen and re-fetches the
 * rows with the same filters — and it would be wrong in the way a copy is
 * always wrong: the filters would be the ones the reader last *saved*, not the
 * half-typed search and the unsaved narrowing they actually had, and the scroll
 * would start at the top. `ScreenHost` keeps its list mounted behind an open
 * record (`v-show`, not `v-if`) precisely so that closing one comes back to the
 * same rows. So the window does not draw a list: it is where that list is
 * drawn, and a `<Teleport>` is what moves it there. Same component, same rows,
 * same selection, same unsaved filter, no second request.
 *
 * Which means the window's contents belong to whichever screen is open, and it
 * closes when that screen goes. A window holding a list that is no longer
 * anywhere is a window holding the last thing it saw.
 */
import { reactive } from 'vue'

import { close, onDesk, open } from '@/modules/onespace/lib/desk/windows'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * Its place on the desk. One at a time: there is one list behind one record.
 *
 * `pip` and not `peek`, which is the better English word and is taken:
 * `composables/usePeek.js` is a *record* opened from inside another one, in a
 * drawer, and that one goes in `docs/DESKTOP.md` stage 4 — replaced by this.
 * Two things called peek until then is how the wrong one gets closed.
 */
export const PIP = 'pip'

/**
 * Where the list lands. An id and not a ref, because `<Teleport to>` takes a
 * selector — and one written in two files is one that goes stale in one of
 * them.
 */
export const BODY = 'desk-pip-body'

/**
 * What the window is called, which is the screen's own name.
 *
 * Never empty, because the window is mounted from the moment the app is —
 * `PipWindow.vue` says why — so its close button exists, and is named, before
 * anybody has opened anything. Empty, that name read "Close , beside what you
 * are reading", which is the sort of thing only a screen reader ever hears.
 */
export const pip = reactive({ label: __('The list') })

/** Whether the list is in the window rather than on the page. Folded counts:
 *  a folded window still holds what was put in it. */
export function inPip() {
  return onDesk(PIP)
}

export function openPip(label = '') {
  pip.label = label || __('The list')
  // Named and glyphed for the dock, which has nothing else to draw it from:
  // no app tile stands for this window, so the only thing that knows what is
  // in it is whoever opened it.
  open(PIP, { label: pip.label, icon: 'lucide-list' })
}

export function closePip() {
  close(PIP)
}

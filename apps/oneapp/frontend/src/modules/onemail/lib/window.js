/**
 * OneMail's place on the desk, and which conversation it is showing.
 *
 * `docs/DESKTOP.md` stage 6, the half that was still to come. Mail was the
 * last of the everyday surfaces that took the screen away: reading one message
 * about a project meant leaving the project, and coming back was the back
 * button and a re-read. Which is exactly what a window is for — and mail more
 * than any of them, because a reply is almost always about something else you
 * are looking at.
 *
 * The route stays as the maximised case, so `/one/mail?thread=…` still opens a
 * conversation for somebody a colleague sent it to.
 *
 * Its own module for the reason `onestorage/lib/window.js` is one: the dock,
 * the window and anything that wants to open a message beside what somebody is
 * doing all name the same thing, and `apps.js` — which knows about every app —
 * must not import a component to find out what one is called.
 */
import { reactive } from 'vue'

import { press } from '@/modules/onespace/lib/desk/windows'

/** The window id, which is also its dock tile and its remembered corner. */
export const MAIL = 'onemail'

/**
 * Which folder it is in and which conversation is open, which is not the
 * address.
 *
 * The page keeps both in the URL because a conversation is a place somebody
 * can be sent to. A window has no address, so it keeps them here — and keeps
 * them across a fold, because folding a window is putting it down rather than
 * closing it.
 */
const WHERE = reactive({ folder: 'all', thread: '' })

export const whereIs = () => WHERE

/** Look somewhere, without touching the desk. */
export function goTo(where) {
  WHERE.folder = where?.folder || 'all'
  // Only what the caller said. Changing folder closes the conversation, the
  // same way it does on the page: a thread in Sent is not one in Archive.
  WHERE.thread = where?.thread || ''
}

/**
 * Open it, at a folder or a conversation if you say so, and bring it forward.
 *
 * The one way in from outside the module. `press` unfolds a window that was
 * put away and raises one that was behind something, which is what somebody
 * pressing Mail means whichever of those was true.
 */
export function showMail(where, how = {}) {
  if (where) goTo(where)
  press(MAIL, how)
}

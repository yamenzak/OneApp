/**
 * OneCloud's place on the desk, and where it is looking.
 *
 * Its own module so that the dock, the window and anything that wants to open
 * a folder beside what somebody is doing all name it the same thing — and so
 * that `apps.js`, which knows about every app, does not have to import a
 * component to find out what one is called.
 */
import { reactive } from 'vue'

import { press } from '@/modules/onespace/lib/desk/windows'

/** The window id, which is also its dock tile and its remembered corner. */
export const DRIVE = 'onestorage'

/**
 * Where the window is looking, which is not the address.
 *
 * `docs/DESKTOP.md`: position and size are remembered per app, *which* windows
 * are open is not — a pasted link opens the page, not somebody else's desk. A
 * folder somebody opened beside what they were doing is the same kind of fact,
 * so it lives here and the page underneath keeps its own.
 *
 * Here rather than inside `DriveWindow.vue`, because a record's Files tab
 * opens the window *at* somewhere: the state has to be reachable from a
 * component that is not the window and does not mount it.
 *
 * It survives folding, because the window does — the component is mounted for
 * the session and the window's own `v-show` is what hides it.
 */
export const at = reactive({ place: 'home', folder: '' })

/** Look somewhere, without touching the desk. */
export function goTo(where) {
  at.place = where?.place || 'home'
  at.folder = where?.folder || ''
}

/**
 * Open OneCloud, at somewhere if you say so, and bring it forward.
 *
 * The one way in from outside the module. `press` unfolds a window that was
 * put away and raises one that was behind something, which is what somebody
 * pressing "Files" on a record means whichever of those was true.
 */
export function showDrive(where, how = {}) {
  if (where) goTo(where)
  press(DRIVE, how)
}

/**
 * The folder a record's own files are in — `docs/DRIVE.md` §13.
 *
 * A room's id *is* its path: `onestorage/file.py` names the top of one after
 * the record it belongs to, so this is the address rather than a lookup. The
 * Records place walks the same two levels from the other direction.
 */
export function roomOf(doctype, name) {
  return doctype && name ? { place: 'records', folder: `${doctype}/${name}` } : null
}

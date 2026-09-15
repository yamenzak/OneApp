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
 * The four windows this module draws, and what each of them is.
 *
 * One file manager, four doors into it. A document is a `File` and a workbook
 * is a `File`, so "OneWriter" is not a second application over a second store
 * — it is this one, landed on `place=documents`, with its own tile, its own
 * colour and its own corner on the desk. Which is what an applet *is* here:
 * somewhere you keep open beside your work, not a program.
 *
 * Three tiles pointing at one page would be wrong; three windows each holding
 * the same component over a different `where` is the dock doing its job. The
 * dock is this product's tab strip and it already draws a face per thing.
 *
 * The editors draw no rail. OneCloud's rail is the places a file can be, and
 * inside OneWriter there is one place — a rail there would be a column of
 * doors out of the room you just opened. Google Docs has no rail either, for
 * the same reason.
 */
export const APPS = [
  { id: DRIVE, brand: 'onestorage', place: 'start', rail: true },
  { id: 'onedoc', brand: 'onedoc', place: 'documents', rail: false },
  { id: 'onesheet', brand: 'onesheet', place: 'workbooks', rail: false },
  { id: 'onecode', brand: 'onecode', place: 'code', rail: false },
]

/** One of them by its window id, or nothing. */
export const appAt = (id) => APPS.find((one) => one.id === id) || null

/**
 * Where each of them is looking, which is not the address.
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
const WHERE = reactive(Object.fromEntries(
  APPS.map((one) => [one.id, { place: one.place, folder: '' }]),
))

/** Where one of them is looking. */
export const whereIs = (id) => WHERE[id] || WHERE[DRIVE]

/** Look somewhere, without touching the desk. */
export function goTo(where, id = DRIVE) {
  const here = whereIs(id)
  here.place = where?.place || appAt(id)?.place || 'start'
  here.folder = where?.folder || ''
}

/**
 * Open one of them, at somewhere if you say so, and bring it forward.
 *
 * The one way in from outside the module. `press` unfolds a window that was
 * put away and raises one that was behind something, which is what somebody
 * pressing "Files" on a record means whichever of those was true.
 */
export function showDrive(where, how = {}, id = DRIVE) {
  if (where) goTo(where, id)
  press(id, how)
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

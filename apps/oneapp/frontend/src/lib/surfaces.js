/**
 * The three shapes an open record can take, and who decides.
 *
 * It used to be two, and neither was anybody's choice: a phone got a page, a
 * desktop got the pane, and a screen that declared a showcase got a page
 * because the manifest said so. All three of those are still the defaults —
 * they are good defaults — but "how much of the window does this record get"
 * is a preference, and a person reading a long form beside a list they do not
 * need is entitled to take the whole width.
 *
 *   pane    the resizable column beside the list. A record you read *against*
 *           the list: mark this done, glance at the next, come back.
 *   page    the whole content area. A record that is a place rather than a
 *           form, or one somebody chose to open this way.
 *   drawer  an overlay over a page. A record you are looking at *from* another
 *           record — a variation from its job, an invoice from the project it
 *           was raised against — where losing your place is the whole cost.
 *
 * Nothing here asks the viewport. A phone has no room for two of these and
 * `RecordPane` says so itself; this module answers the question a desktop has.
 */

export const PANE = 'pane'
export const PAGE = 'page'
export const DRAWER = 'drawer'

/**
 * Where a record's controls go when it is a page.
 *
 * A page has no header of its own — the trail above the screen is already
 * naming it — so the controls teleport onto that line instead of drawing a
 * second bar under it. Named here rather than written twice, because the two
 * halves are in different components and an id that agrees by coincidence
 * agrees until somebody renames one of them.
 *
 * One target, and it can only ever have one occupant: the page is the record
 * underneath, and the only other record on screen is in the drawer, which
 * never merges.
 */
export const MERGE_TARGET = 'record-controls-on-the-trail'

// Per screen, not per person-and-nothing-else. "A project is a page and a task
// is a pane" is a coherent thing to want, and one global flag cannot hold it.
const KEY = 'onespace.record-surface'

const slot = (spaceCode, screen) => `${KEY}.${spaceCode}/${screen}`

/**
 * What the manifest says, before anybody has an opinion.
 *
 * A screen that draws a record as a hero over its own photograph is asking for
 * the width; every other screen is a form, and a form beside its list is the
 * shape this product has always had.
 */
export function declared(spec) {
  return spec?.view_settings?.showcase ? PAGE : PANE
}

/**
 * The surface a screen's records open on: the reader's answer, else the
 * manifest's.
 *
 * `null` from storage rather than a default, so "never chosen" and "chose the
 * same as the default" stay different — a screen that later starts declaring a
 * showcase should start opening as a page for everyone who never had a view.
 */
export function chosen(spaceCode, screen, spec) {
  return remembered(spaceCode, screen) || declared(spec)
}

export function remembered(spaceCode, screen) {
  if (!spaceCode || !screen) return null
  try {
    const found = window.localStorage.getItem(slot(spaceCode, screen))
    return found === PANE || found === PAGE ? found : null
  } catch {
    // Private browsing, a blocked origin, a quota. A preference nobody can
    // read is a preference nobody set.
    return null
  }
}

/** Remember it, or forget it — `null` puts the screen back on the manifest. */
export function remember(spaceCode, screen, surface) {
  if (!spaceCode || !screen) return
  try {
    if (surface) window.localStorage.setItem(slot(spaceCode, screen), surface)
    else window.localStorage.removeItem(slot(spaceCode, screen))
  } catch {
    // Nothing to do and nothing worth saying: the record still opens, it just
    // opens the way the manifest says next time.
  }
}

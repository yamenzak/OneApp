/**
 * The three shapes an open record can take, and who decides.
 *
 *   pane    the resizable column beside the list. A record you read *against*
 *           the list: mark this done, glance at the next, come back.
 *   page    the whole content area. A record that is a place rather than a
 *           form, or one somebody chose to open this way.
 *   drawer  an overlay over a page. A record you are looking at *from* another
 *           record, where losing your place is the whole cost.
 *
 * A phone gets a page, a desktop the pane, and a screen that declares a
 * showcase a page — all still the defaults, but "how much of the window does
 * this record get" is a preference. Nothing here asks the viewport: a phone has
 * no room for two of these and `RecordPane` says so itself.
 */

import { forget, recall, remember as keep } from '@/shared/lib/url/remember'
export const PANE = 'pane'
export const PAGE = 'page'
export const DRAWER = 'drawer'

/**
 * Where a record's controls go when it is a page: the trail above is already
 * naming it, so they teleport onto that line rather than drawing a second bar.
 * Named here rather than written twice, because an id that agrees by
 * coincidence agrees until somebody renames one of them.
 */
export const MERGE_TARGET = 'record-controls-on-the-trail'

// Per screen, not per person-and-nothing-else. "A project is a page and a task
// is a pane" is a coherent thing to want, and one global flag cannot hold it —
// so the space and the screen narrow the remembered key.
const KEY = 'record.surface'

/**
 * What the manifest says, before anybody has an opinion. A screen that draws a
 * record as a hero over its own photograph is asking for the width.
 */
export function declared(spec) {
  return spec?.view_settings?.showcase ? PAGE : PANE
}

/**
 * The surface a screen's records open on: the reader's answer, else the
 * manifest's. `null` from storage rather than a default, so a screen that later
 * starts declaring a showcase starts opening as a page for everyone who never
 * had a view.
 */
export function chosen(spaceCode, screen, spec) {
  return remembered(spaceCode, screen) || declared(spec)
}

export function remembered(spaceCode, screen) {
  if (!spaceCode || !screen) return null
  const found = recall(KEY, spaceCode, screen)
  return found === PANE || found === PAGE ? found : null
}

/** Remember it, or forget it — `null` puts the screen back on the manifest. */
export function remember(spaceCode, screen, surface) {
  if (!spaceCode || !screen) return
  if (surface) keep(KEY, surface, spaceCode, screen)
  else forget(KEY, spaceCode, screen)
}

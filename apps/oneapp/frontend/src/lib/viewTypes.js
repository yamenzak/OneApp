import { defineAsyncComponent } from 'vue'

/**
 * The ways a screen can be looked at.
 *
 * A screen declares which of these it offers and in what order; the first is
 * what it opens with. Only some are built — the rest are declared here so a
 * manifest can name one before the body exists, and so the vocabulary lives in
 * one place rather than in three components.
 *
 * `built: false` is not a placeholder for tidiness: `viewTypesOf` drops them,
 * so a manifest that names `calendar` today gets a list rather than an empty
 * screen, and starts offering the calendar the day one ships.
 */
export const VIEW_TYPES = {
  list: {
    label: 'List',
    icon: 'lucide-list',
    built: true,
    body: () => import('../components/screen/ListBody.vue'),
  },
  board: {
    label: 'Board',
    icon: 'lucide-columns-3',
    built: true,
    body: () => import('../components/screen/BoardBody.vue'),
  },
  calendar: { label: 'Calendar', icon: 'lucide-calendar', built: false },
  dashboard: {
    label: 'Dashboard',
    icon: 'lucide-chart-column',
    built: true,
    body: () => import('../components/screen/DashboardBody.vue'),
  },
  grid: {
    label: 'Grid',
    icon: 'lucide-layout-grid',
    built: true,
    body: () => import('../components/screen/CardsBody.vue'),
  },
  map: { label: 'Map', icon: 'lucide-map', built: false },
}

export const DEFAULT_VIEW_TYPE = 'list'

/**
 * View types that are a way of reading one field, and are nothing without it.
 *
 * A board is columns of a status: a screen that names no `status_field` has no
 * columns to make, and a board of one column called "everything" is not a
 * board. The manifest check catches declaring one anyway; this drops it from
 * the sidebar so a screen offers a board only where there is one to offer.
 * `spaceview._view_types` is the same rule on the server.
 */
export const NEEDS_STATUS = ['board']

/**
 * View types that are nothing without something declared for them to draw.
 *
 * A dashboard is its widgets: a screen that offers one and declares none opens
 * on an empty page. The server drops the type for the same reason — this is
 * the half that keeps it out of the sidebar, so a screen offers a dashboard
 * only where there is one to offer.
 */
export const NEEDS_WIDGETS = ['dashboard']

/**
 * The types that draw a record as a card rather than as a line.
 *
 * A board and a grid share the card and differ only in how the cards are laid
 * out — see `lib/cards.js`. What they share here is the question the gear
 * opens: not "which columns and how wide", which is meaningless without a
 * table, but "what does a card say".
 *
 * `spaceview.CARD_VIEW_TYPES` is the same list.
 */
export const CARD_VIEW_TYPES = ['board', 'grid']

/**
 * The types one screen offers, in order, filtered to what this build renders.
 *
 * Always at least one. A screen that declares nothing, or declares only types
 * nobody has built, is a list — an empty screen would be the alternative and
 * that is never the better answer.
 */
export function viewTypesOf(screen) {
  const declared = String(screen?.view_types || '')
    .split(',')
    .map((type) => type.trim().toLowerCase())
    .filter((type) => VIEW_TYPES[type]?.built)
    .filter((type) => hasColumnField(screen) || !NEEDS_STATUS.includes(type))
  return declared.length ? [...new Set(declared)] : [DEFAULT_VIEW_TYPE]
}

/**
 * Whether a screen names a field a board could make columns of.
 *
 * `status_field` is the usual answer and the one a manifest should give. A
 * screen with no status but an obvious grouping field may name that instead,
 * in its own `view_settings`. Either way this is a declaration check — the
 * fieldtype is checked on the server, where there are columns to check against
 * — and `spaceview._has_column_field` is the same rule.
 *
 * A reader's own choice is deliberately not here: a saved view narrows what a
 * screen offers, it cannot add a view type the screen never offered.
 */
function hasColumnField(screen) {
  if (String(screen?.status_field || '').trim()) return true
  let settings = screen?.view_settings
  if (typeof settings === 'string') {
    try {
      settings = JSON.parse(settings || 'null')
    } catch {
      return false
    }
  }
  return !!String(settings?.board?.column_field || '').trim()
}

/**
 * The component that draws one view type.
 *
 * Async, so a screen only loads the body it is actually rendering — the point
 * of the split is that adding a board does not make every list heavier. Falls
 * back to the list, which is also what the server does, so the two cannot
 * disagree about what an unknown type means.
 */
export function bodyFor(type) {
  const found = VIEW_TYPES[type]
  return defineAsyncComponent(
    found?.body || VIEW_TYPES[DEFAULT_VIEW_TYPE].body,
  )
}

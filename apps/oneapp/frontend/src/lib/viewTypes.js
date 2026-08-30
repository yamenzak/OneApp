import { defineAsyncComponent } from 'vue'

/**
 * The ways a screen can be looked at.
 *
 * A screen declares which of these it offers and in what order; the first is
 * what it opens with. Only `list` is built — the rest are declared here so a
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
  board: { label: 'Board', icon: 'lucide-columns-3', built: false },
  calendar: { label: 'Calendar', icon: 'lucide-calendar', built: false },
  grid: { label: 'Grid', icon: 'lucide-layout-grid', built: false },
  map: { label: 'Map', icon: 'lucide-map', built: false },
}

export const DEFAULT_VIEW_TYPE = 'list'

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
  return declared.length ? [...new Set(declared)] : [DEFAULT_VIEW_TYPE]
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

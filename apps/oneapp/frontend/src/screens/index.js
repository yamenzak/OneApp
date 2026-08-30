/**
 * The escape hatch: screens an app writes itself.
 *
 * Most of an app is a list of records and one of those records open, and that
 * shape comes out of the manifest with no code here — a screen names a doctype and
 * some fieldnames, and OneSpace renders it from the tenant site's own metadata.
 *
 * What is registered here is the rest: a dashboard, a wizard, a calendar,
 * anything a list cannot be. A screen whose `component` matches a key below gets
 * that component instead, with the app code and screen slug as props, and nothing
 * else about the screen applies.
 *
 * Keyed `spaceCode/screen` so two apps can each have an `overview` and neither has
 * to know about the other. Lazy so an app nobody opened costs nothing to load.
 */
export const APP_COMPONENTS = {
  // 'crm/pipeline': () => import('./crm/Pipeline.vue'),
}

export function screenComponent(name) {
  return APP_COMPONENTS[name] || null
}

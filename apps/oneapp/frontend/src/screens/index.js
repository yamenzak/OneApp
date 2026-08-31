import { defineAsyncComponent } from 'vue'

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

  // The operator console's two surfaces that are genuinely not lists.
  // Registered here rather than in the control app because this is where the
  // shell resolves them — `oneapp_control` declares the screens, `oneapp`
  // renders them, and neither has to know more about the other than the key.
  //
  // They call whitelisted methods on the same site, so nothing about them is
  // cross-site: on a tenant, the space that names them does not exist and
  // these are never imported.
  'onespace-ops/readiness': () => import('./ops/Readiness.vue'),
  'onespace-ops/press': () => import('./ops/FrappeCloud.vue'),
  'onespace-ops/tenant': () => import('./ops/Tenant.vue'),

  // The customer's account. Nearly all of it is one workspace's overview,
  // billing and people rather than a list of records, so it is component
  // screens by nature rather than by exception — which is the right shape for
  // it, not a compromise.
  //
  // It lives on the control plane because that is the only place that knows a
  // person owns three tenancies: a tenant site's HMAC secret proves it is
  // *itself* and nothing more.
  'onespace-account/overview': () => import('./account/Overview.vue'),
  'onespace-account/apps': () => import('./account/Apps.vue'),
  'onespace-account/billing': () => import('./account/Billing.vue'),
  'onespace-account/plan': () => import('./account/Plan.vue'),
  'onespace-account/people': () => import('./account/People.vue'),
  'onespace-account/roles': () => import('./account/Roles.vue'),
  'onespace-account/domain': () => import('./account/Domain.vue'),
}

/**
 * The component for a screen, ready to render.
 *
 * `defineAsyncComponent`, not the bare loader. `<component :is>` given a plain
 * function treats it as a *functional component* and renders whatever it
 * returns — so a raw `() => import(…)` renders the string `[object Promise]`
 * where the screen should be, with no error anywhere. This registry held only a
 * commented-out example until the operator console arrived, so the escape hatch
 * had never actually rendered anything.
 *
 * Memoised: `defineAsyncComponent` returns a new wrapper each call, and a new
 * component identity on every render is a screen that remounts — losing its
 * state — whenever anything above it updates.
 */
const resolved = new Map()

export function screenComponent(name) {
  const loader = APP_COMPONENTS[name]
  if (!loader) return null
  if (!resolved.has(name)) resolved.set(name, defineAsyncComponent(loader))
  return resolved.get(name)
}

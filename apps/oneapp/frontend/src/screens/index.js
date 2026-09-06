import { defineAsyncComponent } from 'vue'

/**
 * The escape hatch: screens an app writes itself.
 *
 * Most of an app is a list of records and one of those records open, and that
 * shape comes out of the manifest with no code here. What is registered below
 * is the rest — a dashboard, a wizard, anything a list cannot be. A screen
 * whose `component` matches a key gets that component instead, and nothing else
 * about the screen applies.
 *
 * Keyed `spaceCode/screen` so two apps can each have an `overview`. Lazy, so an
 * app nobody opened costs nothing to load.
 */
export const APP_COMPONENTS = {
  // 'crm/pipeline': () => import('./crm/Pipeline.vue'),

  // The operator console's two surfaces that are genuinely not lists.
  // Registered here rather than in the control app because this is where the
  // shell resolves them. They call whitelisted methods on the same site: on a
  // tenant, the space that names them does not exist.
  'onespace-ops/readiness': () => import('./ops/Readiness.vue'),
  'onespace-ops/press': () => import('./ops/FrappeCloud.vue'),
  'onespace-ops/tenant': () => import('./ops/Tenant.vue'),

  // The customer's account: one workspace's overview, billing and people
  // rather than a list of records. It lives on the control plane because that
  // is the only place that knows a person owns three tenancies.
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
 * `defineAsyncComponent`, not the bare loader: `<component :is>` given a plain
 * function treats it as a *functional component* and renders whatever it
 * returns — so a raw `() => import(…)` renders `[object Promise]` with no error
 * anywhere.
 *
 * Memoised, because a new component identity on every render is a screen that
 * remounts whenever anything above it updates.
 */
const resolved = new Map()

export function screenComponent(name) {
  const loader = APP_COMPONENTS[name]
  if (!loader) return null
  if (!resolved.has(name)) resolved.set(name, defineAsyncComponent(loader))
  return resolved.get(name)
}

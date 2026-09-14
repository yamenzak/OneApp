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
 *
 * A key with **no slash** is the other kind: a screen the *engine* provides,
 * which any space may name. There is one, and it is the one every space wants —
 * a Configuration page. Keying that per space would be the same entry three
 * times today and once more per app after that, which is the shape
 * `docs/UNIFICATION.md` F1 is entirely about.
 */
export const APP_COMPONENTS = {
  // The engine's own. Named by a manifest as `"component": "configuration"`.
  configuration: () => import('@/modules/onespace/screens/Configuration.vue'),

  // One's own front page. The space every workspace has, and the page that
  // replaced a grid of cards you arrived at in order to leave.
  'one/home': () => import('@/modules/onespace/screens/one/Home.vue'),

  // OneHR's, and the first screen in this product written for the person a
  // record is *about* rather than for whoever administers them.
  'onehr/home': () => import('@/modules/onespace/screens/onehr/Home.vue'),

  // And the other side of the same day: taking the register for everybody at
  // once. A component screen that names a doctype, which is how it says who it
  // is for — see `spaceview.resolve`.
  'onehr/roster': () => import('@/modules/onespace/screens/onehr/Roster.vue'),

  // 'crm/pipeline': () => import('@/modules/onespace/screens/crm/Pipeline.vue'),

  // The operator console's surfaces that are genuinely not lists.
  // Registered here rather than in the control app because this is where the
  // shell resolves them. They call whitelisted methods on the same site: on a
  // tenant, the space that names them does not exist.
  //
  // Attention is first on the rail and first here for the same reason: it is
  // the only screen that says something is wrong without being asked. The
  // other twenty-odd are places to go looking.
  'onespace-ops/attention': () => import('@/modules/onespace/screens/ops/Attention.vue'),
  'onespace-ops/readiness': () => import('@/modules/onespace/screens/ops/Readiness.vue'),
  'onespace-ops/press': () => import('@/modules/onespace/screens/ops/FrappeCloud.vue'),
  'onespace-ops/tenant': () => import('@/modules/onespace/screens/ops/Tenant.vue'),

  // The customer's account: the facts about an account that owns several
  // workspaces rather than about any one of them. People, Roles and Domain
  // used to be here and are now settings tabs inside the workspace they are
  // about — `docs/MARKETPLACE.md` §2 is the dividing question.
  'onespace-account/overview': () => import('@/modules/onespace/screens/account/Overview.vue'),
  'onespace-account/apps': () => import('@/modules/onespace/screens/account/Apps.vue'),
  'onespace-account/billing': () => import('@/modules/onespace/screens/account/Billing.vue'),
  'onespace-account/plan': () => import('@/modules/onespace/screens/account/Plan.vue'),

  // OneMobility's screens that are not lists: a map of a moving fleet
  // with a time scrubber, the aggregate tier as plots, and the same tier read
  // about a day that has not happened. Registered here for the same reason the
  // operator's are — this is where the shell resolves a `component`. None of
  // them is a dashboard view, because a dashboard widget counts a doctype's
  // rows and the fact tables are outside the document system on purpose.
  'onemobility/network': () => import('@/modules/onemobility/components/Network.vue'),
  'onemobility/insights': () => import('@/modules/onemobility/components/Insights.vue'),
  'onemobility/outlook': () => import('@/modules/onemobility/components/Outlook.vue'),
  'onemobility/plan': () => import('@/modules/onemobility/components/Timetable.vue'),
  'onemobility/protocols': () => import('@/modules/onemobility/components/Protocols.vue'),
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

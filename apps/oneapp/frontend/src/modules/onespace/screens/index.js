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

  // And the third engine screen: a doctype with exactly one document. Frappe
  // calls it a Single and the list engine has nothing to say about one — no
  // list, no record id, no New button — so every screen mechanism here passed
  // straight over them and a Single was desk-only. A space names the doctype
  // and the fields and gets the form; `oneapp/onespace/singles.py` says what a
  // verb beyond Save is and why a manifest cannot name one.
  single: () => import('@/modules/onespace/screens/Single.vue'),

  // And the other one every space wants: a front page. Its blocks are other
  // screens of the same space, which is what makes it role-specific without
  // anything here knowing what a role is — `onespace/homepage.py`.
  home: () => import('@/modules/onespace/screens/SpaceHome.vue'),

  // One's own front page. The space every workspace has, and the page that
  // replaced a grid of cards you arrived at in order to leave.
  'one/home': () => import('@/modules/onespace/screens/one/Home.vue'),

  // And One's other one: what is waiting on this reader to say yes or no,
  // across every space at once. The engine has driven Frappe's workflow since
  // the record shell was built and the framework has been writing a
  // `Workflow Action` per approver the whole time — nobody read them back, so
  // approval worked one record at a time for somebody who already knew which
  // record to open. `oneapp/onespace/waiting.py`.
  'one/waiting': () => import('@/modules/onespace/screens/one/Waiting.vue'),

  // OnePeople's, and the first screen in this product written for the person a
  // record is *about* rather than for whoever administers them.
  'onehr/home': () => import('@/modules/onespace/screens/onehr/Home.vue'),

  // And the other side of the same day: taking the register for everybody at
  // once. A component screen that names a doctype, which is how it says who it
  // is for — see `spaceview.resolve`.
  'onehr/roster': () => import('@/modules/onespace/screens/onehr/Roster.vue'),

  // And the three HRMS bulk tools: a Single's own form used as a question —
  // describe the people, find out who that is, tick the ones you mean, and do
  // it to them. The form half is `single` above; what is theirs is the finder,
  // which is the value. `oneapp/onehr/tools.py` says why that is one file.
  'onehr/allocate': () => import('@/modules/onespace/screens/onehr/Tool.vue'),
  'onehr/assign-shifts': () => import('@/modules/onespace/screens/onehr/Tool.vue'),
  'onehr/assign-structures': () => import('@/modules/onespace/screens/onehr/Tool.vue'),

  // 'crm/pipeline': () => import('@/modules/onespace/screens/crm/Pipeline.vue'),

  // The operator console's surfaces that are genuinely not lists.
  // Registered here rather than in the control app because this is where the
  // shell resolves them. They call whitelisted methods on the same site: on a
  // tenant, the space that names them does not exist.
  //
  // Attention is first on the rail and first here for the same reason: it is
  // the only screen that says something is wrong without being asked. The
  // other twenty-odd are places to go looking.
  // OneBook's three statements. One component keyed three times, like
  // OnePeople's five HRMS tools above: a trial balance, a profit and loss and
  // a balance sheet are one shape — an indented chart of accounts with a
  // column per period — and which of the three is the screen it is mounted
  // as. `docs/ONEBOOK.md` §1.
  'onebook/trial-balance': () => import('@/modules/onespace/screens/onebook/Statement.vue'),
  'onebook/profit-and-loss': () => import('@/modules/onespace/screens/onebook/Statement.vue'),
  'onebook/balance-sheet': () => import('@/modules/onespace/screens/onebook/Statement.vue'),

  // And the two ageings, which are one component twice over for the same
  // reason: ERPNext's receivable and payable reports return the same row, so
  // which side this is arrives as the screen it is mounted as.
  // `docs/ONEBOOK.md` §4.
  'onebook/owed-to-us': () => import('@/modules/onespace/screens/onebook/Owing.vue'),
  'onebook/owed-by-us': () => import('@/modules/onespace/screens/onebook/Owing.vue'),

  // And the bank feed turned into a reconciliation: two lists side by side
  // where the right-hand one is a function of the row selected in the left.
  // More obviously not a view type than the statements are — a view type is a
  // rendering of rows a screen narrowed to, and this is a ranking against one
  // of them. `docs/ONEBOOK.md` §3.
  'onebook/reconcile': () => import('@/modules/onespace/screens/onebook/Reconcile.vue'),

  'oneadmin/attention': () => import('@/modules/onespace/screens/ops/Attention.vue'),
  'oneadmin/readiness': () => import('@/modules/onespace/screens/ops/Readiness.vue'),
  'oneadmin/press': () => import('@/modules/onespace/screens/ops/FrappeCloud.vue'),
  'oneadmin/tenant': () => import('@/modules/onespace/screens/ops/Tenant.vue'),

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

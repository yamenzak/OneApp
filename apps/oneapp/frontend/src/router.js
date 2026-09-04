import { createRouter, createWebHistory } from 'vue-router'
import { session, sessionReady } from './lib/session'

const routes = [
  { path: '/', name: 'Launcher', component: () => import('./pages/Launcher.vue') },
  {
    path: '/space/:spaceCode',
    name: 'Screen',
    component: () => import('./pages/ScreenHost.vue'),
    props: true,
    // The app host is a pane, not a page: its list is a fixed-height grid that
    // owns both scrollbars, so the horizontal one sits at the bottom of the
    // screen instead of at the bottom of a table somebody has to scroll to
    // find. `pane` turns the shell's own page scroll off for this route.
    meta: { pane: true },
  },
  { path: '/account', name: 'Account', component: () => import('./pages/Account.vue') },
  {
    // Mail belongs to the workspace rather than to any one space — the
    // addresses a person holds do not change when they switch space — so it is
    // a route beside the account page rather than a screen inside a space.
    path: '/mail',
    name: 'Mail',
    component: () => import('./pages/Mail.vue'),
    // Two columns and a reading pane, each with its own scroller. Same reason
    // as the screen host: without this the shell scrolls the page and the list
    // never keeps its header.
    meta: { pane: true },
  },
  {
    // Files belong to the workspace rather than to any one space — an
    // attachment on a project and a drawing nobody has filed are the same row
    // in the same table — so this is a route beside Mail rather than a screen
    // inside a space.
    path: '/files',
    name: 'Drive',
    component: () => import('./pages/Drive.vue'),
    // A rail, a list and its own scroller, same as the screen host: without
    // this the shell scrolls the page and the list loses its header.
    meta: { pane: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('./pages/NotFound.vue'),
  },
]

const router = createRouter({
  // Matches website_route_rules in hooks.py — the Vue router owns /one.
  history: createWebHistory('/one'),
  routes,
})

router.beforeEach(async (to) => {
  // The resource fires on setup; wait for the first response before deciding.
  // `sessionReady` rather than the resource's own promise, which is renewed
  // after every response and would hang every navigation after the first.
  await sessionReady

  if (!session.isLoggedIn) {
    // Hand back to Frappe's own login, which knows how to return here.
    window.location.href = `/login?redirect-to=${encodeURIComponent(
      window.location.pathname,
    )}`
    return false
  }

  // Entitlement is enforced server-side by role. This only avoids rendering a
  // shell for something the user will be refused anyway.
  if (to.name === 'Screen' && !session.hasSpace(to.params.spaceCode)) {
    return { name: 'Launcher' }
  }

  return true
})

export default router

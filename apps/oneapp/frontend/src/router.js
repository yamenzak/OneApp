import { createRouter, createWebHistory } from 'vue-router'
import { session, sessionReady } from '@/lib/shell/session'

const routes = [
  { path: '/', name: 'Launcher', component: () => import('./pages/Launcher.vue') },
  {
    path: '/space/:spaceCode',
    name: 'Screen',
    component: () => import('./pages/ScreenHost.vue'),
    props: true,
    // The app host is a pane, not a page: its list is a fixed-height grid that
    // owns both scrollbars, so the horizontal one sits at the bottom of the
    // screen. `pane` turns the shell's own page scroll off for this route.
    meta: { pane: true },
  },
  { path: '/account', name: 'Account', component: () => import('./pages/Account.vue') },
  {
    // What this workspace could add. A page rather than a dialog because it is
    // a place you browse and come back to, and because a card that starts a
    // several-minute install wants a URL somebody can return to.
    path: '/add',
    name: 'Marketplace',
    component: () => import('./pages/Marketplace.vue'),
  },
  {
    // Mail belongs to the workspace rather than to any one space — the
    // addresses a person holds do not change when they switch space.
    path: '/mail',
    name: 'Mail',
    component: () => import('./pages/Mail.vue'),
    // Two columns and a reading pane, each with its own scroller.
    meta: { pane: true },
  },
  {
    // Files belong to the workspace too: an attachment on a project and a
    // drawing nobody has filed are the same row in the same table.
    path: '/files',
    name: 'Drive',
    component: () => import('./pages/Drive.vue'),
    // A rail, a list and its own scroller, same as the screen host.
    meta: { pane: true },
  },
  {
    // The diary: everything the reader has with a date on it, from every
    // calendar this workspace has. The merge is the server's, in
    // `oneapp_core/diary.py`.
    path: '/calendar',
    name: 'Calendar',
    component: () => import('./pages/Diary.vue'),
    // A rail, a grid and its own scroller: the shell must not add a second.
    meta: { pane: true },
  },
  {
    // The assistant belongs to the workspace, like Mail and Files: what it can
    // read follows the reader's roles across every space, not one of them.
    // The open thread is `?chat=`, so a conversation can be linked to.
    path: '/chat',
    name: 'Chat',
    component: () => import('./pages/Chat.vue'),
    // A rail, a transcript with its own scroller and a composer pinned under
    // it: a page scroll on top would move the composer off screen.
    meta: { pane: true },
  },
  {
    // A sheet is a File, so this is not a second kind of thing with a second
    // kind of address: `:name` is the File row.
    path: '/sheets/:name',
    name: 'Sheet',
    component: () => import('./pages/Sheet.vue'),
    props: true,
    // A grid owns both its scrollbars, and it gets the window: see `chrome` on
    // `AppShell` for why an editor draws no rail and no sidebar.
    meta: { pane: true, focused: true },
  },
  {
    // A document is a File too, so this is the same kind of address a sheet
    // has. What opens behind it — the prose editor or the plain-text one — is
    // what the file is, which only the server knows.
    path: '/docs/:name',
    name: 'Doc',
    component: () => import('./pages/Doc.vue'),
    props: true,
    // The editor owns its own scroller, and a page scroll under it would put
    // the toolbar off screen the moment anybody typed past the fold. It gets
    // the window too — same reason a sheet does.
    meta: { pane: true, focused: true },
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

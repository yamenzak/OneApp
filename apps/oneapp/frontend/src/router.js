import { createRouter, createWebHistory } from 'vue-router'
import { session, sessionResource } from './lib/session'

const routes = [
  { path: '/', name: 'Launcher', component: () => import('./pages/Launcher.vue') },
  {
    path: '/app/:appCode',
    name: 'App',
    component: () => import('./pages/AppHost.vue'),
    props: true,
  },
  { path: '/account', name: 'Account', component: () => import('./pages/Account.vue') },
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
  await sessionResource.promise

  if (!session.isLoggedIn) {
    // Hand back to Frappe's own login, which knows how to return here.
    window.location.href = `/login?redirect-to=${encodeURIComponent(
      window.location.pathname,
    )}`
    return false
  }

  // Entitlement is enforced server-side by role. This only avoids rendering a
  // shell for something the user will be refused anyway.
  if (to.name === 'App' && !session.hasApp(to.params.appCode)) {
    return { name: 'Launcher' }
  }

  return true
})

export default router

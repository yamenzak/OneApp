import { createRouter, createWebHistory } from 'vue-router'
import { setup } from './lib/setup'

// Two surfaces, one bundle. `/admin` is the staff console; `/portal` is what a
// customer sees. They share a build so the component library, error handling and
// socket wiring can never drift apart, and they are separate Frappe website
// routes so each gets its own server-side guard (see www/admin.py, www/portal.py).
//
// Because one bundle is served from two paths, the history base is '/' and every
// route spells out its own prefix. A base of '/admin' would make the router
// mis-resolve every URL under /portal.
const adminRoutes = [
  { path: '/admin', redirect: '/admin/tenants' },
  { path: '/admin/setup', name: 'Setup', component: () => import('./pages/Setup.vue') },
  { path: '/admin/tenants', name: 'Tenants', component: () => import('./pages/Tenants.vue') },
  {
    path: '/admin/tenants/:name',
    name: 'Tenant',
    component: () => import('./pages/Tenant.vue'),
    props: true,
  },
  { path: '/admin/shards', name: 'Shards', component: () => import('./pages/Shards.vue') },
  { path: '/admin/jobs', name: 'Jobs', component: () => import('./pages/Jobs.vue') },
]

const portalRoutes = [
  { path: '/portal', redirect: '/portal/account' },
  {
    path: '/portal/signup',
    name: 'Signup',
    component: () => import('./pages/signup/SignupPage.vue'),
  },
  {
    path: '/portal/welcome',
    name: 'SignupWelcome',
    component: () => import('./pages/signup/SignupWelcome.vue'),
  },
  {
    path: '/portal/account',
    name: 'Account',
    component: () => import('./pages/account/AccountLayout.vue'),
  },
  {
    // A customer with several workspaces gets one addressable URL each, so the
    // switcher can deep-link and a bookmark keeps working.
    path: '/portal/account/:workspace',
    name: 'AccountWorkspace',
    component: () => import('./pages/account/AccountLayout.vue'),
    props: true,
  },
]

const routes = [
  { path: '/', redirect: '/admin' },
  ...adminRoutes.map((r) => ({ ...r, meta: { ...r.meta, surface: 'admin' } })),
  ...portalRoutes.map((r) => ({ ...r, meta: { ...r.meta, surface: 'portal' } })),
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('./pages/NotFound.vue'),
    meta: { surface: 'admin' },
  },
]

const router = createRouter({ history: createWebHistory('/'), routes })

router.beforeEach(async (to) => {
  // The readiness gate is a staff concern. Running it on the portal would both
  // leak configuration state to customers and block signup behind a call they
  // are not allowed to make.
  if (to.meta.surface !== 'admin') return true

  if (!setup.checks.length && !setup.error) await setup.load()

  // Until the blocking configuration exists there is nothing useful to do here
  // and provisioning would fail partway. Send everything to Setup.
  if (!setup.canProvision && to.name !== 'Setup') {
    return { name: 'Setup' }
  }

  return true
})

export default router

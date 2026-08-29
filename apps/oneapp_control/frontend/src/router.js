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
    meta: { chrome: false },
    component: () => import('./pages/signup/SignupPage.vue'),
  },
  {
    path: '/portal/welcome',
    name: 'SignupWelcome',
    meta: { chrome: false },
    component: () => import('./pages/signup/SignupWelcome.vue'),
  },
  {
    path: '/portal/account',
    name: 'Account',
    component: () => import('./pages/account/AccountResolve.vue'),
  },
  // A customer with several workspaces gets one addressable URL each, so the
  // rail can deep-link and a bookmark keeps working. Each section is its own
  // route rather than a tab: the sidebar entry has to be linkable, and a tab
  // index is not something you can send someone.
  {
    path: '/portal/account/:workspace',
    redirect: (to) => `/portal/account/${to.params.workspace}/overview`,
  },
  {
    path: '/portal/account/:workspace/overview',
    name: 'AccountOverview',
    component: () => import('./pages/account/AccountOverview.vue'),
    props: true,
  },
  {
    path: '/portal/account/:workspace/billing',
    name: 'AccountBilling',
    component: () => import('./pages/account/AccountBilling.vue'),
    props: true,
  },
  {
    path: '/portal/account/:workspace/apps',
    name: 'AccountApps',
    component: () => import('./pages/account/AccountApps.vue'),
    props: true,
  },
  {
    path: '/portal/account/:workspace/plan',
    name: 'AccountPlan',
    component: () => import('./pages/account/AccountPlan.vue'),
    props: true,
  },
  {
    path: '/portal/account/:workspace/team',
    name: 'AccountTeam',
    component: () => import('./pages/account/AccountTeam.vue'),
    props: true,
  },
  {
    path: '/portal/account/:workspace/domain',
    name: 'AccountDomain',
    component: () => import('./pages/account/AccountDomain.vue'),
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

  // Opening the console with nowhere in particular in mind lands on Readiness
  // while it is unconfigured, because that is the only thing worth doing. Only
  // that default landing, though: `redirectedFrom` is set when we chose the
  // destination ourselves, so a typed or bookmarked URL is still honoured.
  //
  // Redirecting *every* admin route made the console look broken: tapping
  // Tenants or Shards bounced straight back to Readiness with nothing said,
  // which reads as a dead button rather than as a gate. The pages are useful
  // unconfigured — the tenant list is empty, the shard list is where you add
  // the first shard — the actions that would fail are already disabled with a
  // reason on the page, and provisioning is refused server-side by
  // assert_ready_to_provision. Nothing was protected by the bounce.
  const landing = ['/', '/admin'].includes(to.redirectedFrom?.path)
  if (landing && !setup.canProvision && to.name !== 'Setup') {
    return { name: 'Setup' }
  }

  return true
})

export default router

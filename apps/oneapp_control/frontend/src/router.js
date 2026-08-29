import { createRouter, createWebHistory } from 'vue-router'
import { setup } from './lib/setup'

const routes = [
  { path: '/', redirect: '/tenants' },
  { path: '/setup', name: 'Setup', component: () => import('./pages/Setup.vue') },
  { path: '/tenants', name: 'Tenants', component: () => import('./pages/Tenants.vue') },
  {
    path: '/tenants/:name',
    name: 'Tenant',
    component: () => import('./pages/Tenant.vue'),
    props: true,
  },
  { path: '/shards', name: 'Shards', component: () => import('./pages/Shards.vue') },
  { path: '/jobs', name: 'Jobs', component: () => import('./pages/Jobs.vue') },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('./pages/NotFound.vue'),
  },
]

// Matches frontendRoute in vite.config.js — the plugin serves the SPA there.
const router = createRouter({ history: createWebHistory('/admin'), routes })

router.beforeEach(async (to) => {
  if (!setup.checks.length && !setup.error) await setup.load()

  // Until the blocking configuration exists, there is nothing useful to do here
  // and provisioning would fail partway. Send everything to Setup.
  if (!setup.canProvision && to.name !== 'Setup') {
    return { name: 'Setup' }
  }

  return true
})

export default router

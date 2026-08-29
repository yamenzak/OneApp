<template>
  <FrappeUIProvider>
    <!-- Signup and the welcome screen are their own full-bleed pages: a visitor
         with no session has no workspaces to put in a rail and no sidebar worth
         showing. Everything else gets the shell. -->
    <router-view v-if="bare" :key="$route.fullPath" />

    <div v-else-if="!ready" class="grid h-screen place-items-center">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <AppShell
      v-else
      :apps="railApps"
      :active-app="activeWorkspace"
      :nav-items="navItems"
      :menu-items="menuItems"
    >
      <template #sidebar>
        <AppSidebar v-if="isAdmin" />
        <PortalSidebar v-else />
      </template>

      <router-view :key="$route.fullPath" />
    </AppShell>

    <!-- Outside the shell so it survives a layout swap, and a dialog rather than
         a route because settings overlay whatever you were doing — closing should
         put you back, not navigate you away. -->
    <SettingsShell v-if="isAdmin" />
  </FrappeUIProvider>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import AppSidebar from './components/AppSidebar.vue'
import PortalSidebar from './components/PortalSidebar.vue'
import SettingsShell from './components/settings/SettingsShell.vue'
import { setup } from './lib/setup'
import { openSettings } from './lib/settings'
import { ADMIN_APP, TENANT_APP } from './lib/brand'
import { workspaces } from './lib/customer'

const route = useRoute()
const isAdmin = computed(() => route.meta.surface === 'admin')
const bare = computed(() => route.meta.chrome === false)

// The console renders as soon as readiness is known — including when it reports
// the control plane is unconfigured, which is exactly when Setup matters. The
// portal waits on its own load instead; readiness is not the customer's call.
const ready = computed(() =>
  isAdmin.value ? !setup.loading || setup.checks.length > 0 : !workspaces.loading,
)

// The rail carries workspaces on the portal. The console is a single surface, so
// it passes none and AppShell renders no rail — a one-item switcher is worse
// than no switcher.
const railApps = computed(() => {
  if (isAdmin.value) return []
  return workspaces.list.map((w) => ({
    key: w.name,
    label: w.tenant_name,
    description: w.plan,
    to: { name: 'AccountOverview', params: { workspace: w.name } },
  }))
})

const activeWorkspace = computed(() => (isAdmin.value ? '' : workspaces.current || ''))

// The phone's bottom bar. Same destinations as the sidebar, which is the point:
// the two must not drift into different products.
const navItems = computed(() => {
  if (isAdmin.value) {
    return [
      { label: 'Tenants', icon: 'lucide-users', to: { name: 'Tenants' } },
      { label: 'Jobs', icon: 'lucide-activity', to: { name: 'Jobs' } },
      { label: 'Shards', icon: 'lucide-server', to: { name: 'Shards' } },
      { label: 'Setup', icon: 'lucide-settings', to: { name: 'Setup' } },
    ]
  }
  const workspace = workspaces.current
  if (!workspace) return []
  return [
    { label: 'Overview', icon: 'lucide-home', to: { name: 'AccountOverview', params: { workspace } } },
    { label: 'Billing', icon: 'lucide-credit-card', to: { name: 'AccountBilling', params: { workspace } } },
    { label: 'People', icon: 'lucide-users', to: { name: 'AccountTeam', params: { workspace } } },
    { label: 'Domain', icon: 'lucide-globe', to: { name: 'AccountDomain', params: { workspace } } },
  ]
})

// Settings live in the sidebar's user menu on a desktop. A phone has no
// sidebar, so without this there is no way to reach them at all — which is
// exactly what an operator hits when the control plane is unconfigured and
// setting it up is the only thing they need to do.
const menuItems = computed(() =>
  isAdmin.value
    ? [{ label: 'Settings', icon: 'lucide-settings', onClick: () => openSettings() }]
    : [],
)

usePageMeta(() => (isAdmin.value ? { title: ADMIN_APP, emoji: '⚙️' } : { title: TENANT_APP }))

// Loaded here rather than in onMounted so neither surface fires the other's
// calls: readiness is not the customer's to ask for, and a visitor at signup has
// no session to list workspaces with.
// Keyed on the surface itself, not on `isAdmin`.
//
// `isAdmin` is a boolean derived from it, and before the router resolves
// `meta.surface` is undefined — so on the portal the derived value was `false`
// on the immediate run (where the guard below returns) and `false` again once
// the route resolved. No change, no re-run, and the whole customer surface sat
// on its loading spinner having never called anything.
watch(
  [() => route.meta.surface, bare],
  ([surface, isBare]) => {
    // Until the router has resolved, meta.surface is undefined and every branch
    // below would guess. Guessing sent the admin console at a customer endpoint
    // on first paint, and a real failure there redirects to login.
    if (!surface || isBare) return
    if (surface === 'admin') {
      if (setup.loading && !setup.checks.length) setup.load()
    } else if (!workspaces.list.length) {
      workspaces.load(route.params.workspace || null)
    }
  },
  { immediate: true },
)

// Keep the rail in step with the URL, so back, forward and a pasted link all
// select the workspace the page is actually showing.
watch(
  () => route.params.workspace,
  (name) => {
    if (name && workspaces.list.some((w) => w.name === name)) workspaces.current = name
  },
)
</script>

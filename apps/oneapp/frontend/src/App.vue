<template>
  <FrappeUIProvider>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :apps="railApps"
      :active-app="activeApp"
      :nav-items="navItems"
    >
      <template #sidebar>
        <AppSidebar />
      </template>

      <template #rail-footer>
        <RailAccount />
      </template>

      <router-view :key="$route.fullPath" />
    </AppShell>

    <div v-else-if="sessionResource.error" class="grid h-screen place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-gray-8">
          We couldn't load your workspace
        </p>
        <p class="mt-1.5 text-p-base text-ink-gray-6">This is usually temporary.</p>
        <Button class="mt-4" variant="solid" label="Try again" @click="session.reload()" />
      </div>
    </div>

    <div v-else class="grid h-screen place-items-center">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { TENANT_APP } from './lib/brand'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, Button, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import AppSidebar from './components/AppSidebar.vue'
import RailAccount from './components/RailAccount.vue'
import { session, sessionResource } from './lib/session'

const route = useRoute()

// The rail is the workspace's apps. This is the one place they are enumerated
// for navigation; the sidebar then belongs to whichever is active.
const railApps = computed(() =>
  session.apps.map((app) => ({
    key: app.app_code,
    label: app.app_label,
    description: app.description,
    to: { name: 'App', params: { appCode: app.app_code } },
  })),
)

const activeApp = computed(() => route.params.appCode || '')

// On a phone the rail is gone, so these are the destinations inside the current
// app. Switching apps is the sheet AppShell adds beside them.
const navItems = computed(() => [
  { label: 'Apps', icon: 'lucide-layout-grid', to: { name: 'Launcher' } },
  { label: 'Account', icon: 'lucide-circle-user', to: { name: 'Account' } },
])

usePageMeta(() => ({ title: session.tenant?.name || TENANT_APP }))
</script>

<template>
  <FrappeUIProvider>
    <!-- The staff console: sidebar chrome, gated on configuration readiness. -->
    <template v-if="isAdmin">
      <DesktopShell v-if="ready">
        <template #sidebar>
          <AppSidebar />
        </template>
        <router-view :key="$route.fullPath" />
      </DesktopShell>

      <div v-else class="grid h-screen place-items-center">
        <LoadingIndicator class="size-5 text-ink-gray-5" />
      </div>

      <!-- Outside the v-if chain so it survives the shell mounting, and a dialog
           rather than a route because settings overlay whatever you were doing —
           closing should put you back, not navigate you away. -->
      <SettingsShell />
    </template>

    <!-- The customer portal: no sidebar, no readiness call. A visitor at signup
         has no session yet, so anything staff-shaped here would 403 on load. -->
    <router-view v-else :key="$route.fullPath" />
  </FrappeUIProvider>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, DesktopShell, LoadingIndicator, usePageMeta } from '@/ui'
import AppSidebar from './components/AppSidebar.vue'
import SettingsShell from './components/settings/SettingsShell.vue'
import { setup } from './lib/setup'

const route = useRoute()
const isAdmin = computed(() => route.meta.surface === 'admin')

// The shell renders as soon as readiness is known — including when it reports
// the control plane is unconfigured, which is exactly when Setup matters.
const ready = computed(() => !setup.loading || setup.checks.length > 0)

usePageMeta(() => (isAdmin.value ? { title: 'OneApp Admin', emoji: '⚙️' } : { title: 'OneApp' }))

// Loaded here rather than in onMounted so it never fires on the portal, where
// the readiness endpoint is not the customer's to call.
watch(
  isAdmin,
  (admin) => {
    if (admin && setup.loading && !setup.checks.length) setup.load()
  },
  { immediate: true },
)
</script>

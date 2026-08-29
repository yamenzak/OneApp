<template>
  <FrappeUIProvider>
    <DesktopShell v-if="ready">
      <template #sidebar>
        <AppSidebar />
      </template>
      <router-view :key="$route.fullPath" />
    </DesktopShell>

    <div v-else class="grid h-screen place-items-center">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { FrappeUIProvider, DesktopShell, LoadingIndicator, usePageMeta } from '@/ui'
import AppSidebar from './components/AppSidebar.vue'
import { setup } from './lib/setup'

// The shell renders as soon as readiness is known — including when it says the
// control plane is unconfigured, which is exactly when the Setup page matters.
const ready = computed(() => !setup.loading || setup.checks.length > 0)

usePageMeta(() => ({ title: 'OneApp Admin', emoji: '⚙️' }))

onMounted(() => setup.load())
</script>

<template>
  <FrappeUIProvider>
    <DesktopShell v-if="session.loaded && session.isLoggedIn">
      <template #sidebar>
        <AppSidebar />
      </template>
      <router-view :key="$route.fullPath" />
    </DesktopShell>

    <div v-else-if="sessionResource.error" class="grid h-screen place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base font-medium text-ink-gray-8">
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
import { FrappeUIProvider, DesktopShell, Button, LoadingIndicator, usePageMeta } from '@/ui'
import AppSidebar from './components/AppSidebar.vue'
import { session, sessionResource } from './lib/session'

usePageMeta(() => ({ title: session.tenant?.name || 'OneApp' }))
</script>

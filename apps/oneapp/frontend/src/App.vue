<template>
  <FrappeUIProvider>
    <AppShell v-if="session.loaded && session.isLoggedIn">
      <router-view />
    </AppShell>

    <div v-else-if="sessionResource.error" class="grid min-h-screen place-items-center p-6">
      <div class="max-w-md text-center">
        <p class="text-p-lg font-medium">We couldn't load your workspace</p>
        <p class="mt-2 text-p-base text-ink-gray-6">This is usually temporary.</p>
        <Button class="mt-4" variant="solid" label="Try again" @click="session.reload()" />
      </div>
    </div>

    <div v-else class="grid min-h-screen place-items-center">
      <LoadingIndicator class="h-6 w-6 text-ink-gray-5" />
    </div>
  </FrappeUIProvider>
</template>

<script setup>
import { FrappeUIProvider, Button, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import { session, sessionResource } from './lib/session'

usePageMeta(() => ({ title: session.tenant?.name || 'OneApp' }))
</script>

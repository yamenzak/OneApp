<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <AppShell v-if="session.loaded && session.isLoggedIn">
      <router-view />
    </AppShell>

    <div v-else-if="session.error" class="grid min-h-screen place-items-center p-6">
      <div class="max-w-md text-center">
        <p class="text-lg font-medium">Something went wrong</p>
        <p class="mt-2 text-sm text-gray-600">
          We couldn't load your workspace. This is usually temporary.
        </p>
        <Button class="mt-4" @click="session.refresh()">Try again</Button>
      </div>
    </div>

    <div v-else class="grid min-h-screen place-items-center">
      <LoadingIndicator class="h-6 w-6 text-gray-500" />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { Button, LoadingIndicator } from 'frappe-ui'
import AppShell from './components/AppShell.vue'
import { session } from './lib/session'

onMounted(() => session.load())
</script>

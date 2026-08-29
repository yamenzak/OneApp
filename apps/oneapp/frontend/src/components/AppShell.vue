<template>
  <div class="flex h-screen flex-col">
    <header
      class="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4"
    >
      <div class="flex items-center gap-3">
        <router-link to="/" class="flex items-center gap-2 font-semibold">
          <span
            class="grid h-7 w-7 place-items-center rounded bg-gray-900 text-xs text-white"
          >
            1
          </span>
          <span>{{ session.tenant?.name || 'OneApp' }}</span>
        </router-link>

        <span
          v-if="session.tenant?.status && session.tenant.status !== 'Active'"
          class="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
        >
          {{ session.tenant.status }}
        </span>
      </div>

      <div class="flex items-center gap-4">
        <QuotaMeter />
        <Dropdown :options="userOptions">
          <Button variant="ghost">{{ session.user?.full_name }}</Button>
        </Dropdown>
      </div>
    </header>

    <main class="flex-1 overflow-auto">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Dropdown } from 'frappe-ui'
import QuotaMeter from './QuotaMeter.vue'
import { session } from '../lib/session'

const userOptions = computed(() => [
  { label: 'Account', onClick: () => (window.location.href = '/one/account') },
  // Desk stays available to us for support, and is pointless noise for everyone else.
  ...(session.user?.is_admin
    ? [{ label: 'Desk', onClick: () => (window.location.href = '/app') }]
    : []),
  { label: 'Log out', onClick: () => (window.location.href = '/api/method/logout') },
])
</script>

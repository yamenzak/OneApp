<template>
  <DesktopShell>
    <template #sidebar>
      <Sidebar>
        <div class="px-3 py-4">
          <router-link to="/" class="flex items-center gap-2 px-2">
            <span
              class="grid h-7 w-7 place-items-center rounded bg-surface-gray-7 text-xs text-ink-white"
            >
              1
            </span>
            <span class="truncate text-base font-medium">
              {{ session.tenant?.name || 'OneApp' }}
            </span>
          </router-link>

          <Badge
            v-if="session.tenant?.status && session.tenant.status !== 'Active'"
            class="mx-2 mt-2"
            theme="orange"
            :label="session.tenant.status"
          />

          <nav class="mt-6 flex flex-col gap-0.5">
            <router-link
              v-for="app in session.apps"
              :key="app.app_code"
              :to="`/app/${app.app_code}`"
              class="truncate rounded px-2 py-1.5 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
              active-class="bg-surface-gray-3 font-medium text-ink-gray-9"
            >
              {{ app.app_label }}
            </router-link>
          </nav>
        </div>

        <template #footer>
          <div class="flex items-center justify-between gap-2 px-3 pb-3">
            <QuotaMeter />
            <Dropdown :options="userOptions">
              <Button variant="ghost" :label="session.user?.full_name" />
            </Dropdown>
          </div>
        </template>
      </Sidebar>
    </template>

    <router-view />
  </DesktopShell>
</template>

<script setup>
import { computed } from 'vue'
import { DesktopShell, Sidebar, Badge, Button, Dropdown } from '@/ui'
import QuotaMeter from './QuotaMeter.vue'
import { session } from '../lib/session'

const userOptions = computed(() => [
  { label: 'Account', onClick: () => (window.location.href = '/one/account') },
  // Desk is for us during support, and noise for everyone else.
  ...(session.user?.is_admin
    ? [{ label: 'Desk', onClick: () => (window.location.href = '/app') }]
    : []),
  { label: 'Log out', onClick: () => (window.location.href = '/api/method/logout') },
])
</script>

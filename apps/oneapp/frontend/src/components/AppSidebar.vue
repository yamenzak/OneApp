<template>
  <Sidebar class="border-r border-outline-gray-1">
    <SidebarHeader>
      <div class="flex items-center gap-2 px-1 py-0.5">
        <Avatar :label="session.tenant?.name || 'OneApp'" shape="square" size="lg" />
        <div class="min-w-0">
          <p class="truncate text-base font-medium text-ink-gray-8">
            {{ session.tenant?.name || 'OneApp' }}
          </p>
          <p
            v-if="session.tenant?.status && session.tenant.status !== 'Active'"
            class="truncate text-xs text-ink-amber-3"
          >
            {{ session.tenant.status }}
          </p>
          <p v-else class="truncate text-xs text-ink-gray-5">{{ session.plan || '' }}</p>
        </div>
      </div>
    </SidebarHeader>

    <SidebarSection>
      <SidebarLabel label="Apps" />
      <SidebarItem
        v-for="app in session.apps"
        :key="app.app_code"
        :label="app.app_label"
        :to="`/app/${app.app_code}`"
        :active="$route.params.appCode === app.app_code"
      >
        <template #prefix>
          <Icon :name="app.icon || 'lucide-square'" class="size-4 text-ink-gray-7" />
        </template>
      </SidebarItem>
    </SidebarSection>

    <template #footer>
      <div class="p-2">
        <QuotaMeter class="mb-2" />
        <Dropdown :options="userOptions" placement="top" class="w-full">
          <Button variant="ghost" class="w-full !justify-start">
            <template #prefix>
              <Avatar :label="session.user?.full_name || '?'" size="sm" />
            </template>
            <span class="truncate">{{ session.user?.full_name }}</span>
          </Button>
        </Dropdown>
      </div>
    </template>
  </Sidebar>
</template>

<script setup>
import { computed } from 'vue'
import {
  Sidebar, SidebarHeader, SidebarSection, SidebarLabel, SidebarItem,
  Avatar, Button, Dropdown, Icon,
} from '@/ui'
import QuotaMeter from './QuotaMeter.vue'
import { session } from '../lib/session'

const userOptions = computed(() => [
  { label: 'Account', onClick: () => (window.location.href = '/one/account') },
  // Desk is for support, and noise for everyone else.
  ...(session.user?.is_admin
    ? [{ label: 'Desk', onClick: () => (window.location.href = '/app') }]
    : []),
  { label: 'Log out', onClick: () => (window.location.href = '/api/method/logout') },
])
</script>

<template>
  <Sidebar class="border-r border-outline-gray-1">
    <SidebarHeader>
      <div class="flex items-center gap-2 px-1 py-0.5">
        <Avatar label="OneApp" shape="square" size="lg" />
        <div v-if="!collapsed" class="min-w-0">
          <p class="truncate text-base font-medium text-ink-gray-8">OneApp</p>
          <p class="truncate text-xs text-ink-gray-5">Control plane</p>
        </div>
      </div>
    </SidebarHeader>

    <SidebarSection>
      <SidebarItem
        v-for="item in nav"
        :key="item.to"
        :label="item.label"
        :to="item.to"
        :active="isActive(item.to)"
      >
        <template #prefix>
          <Icon :name="item.icon" class="size-4 text-ink-gray-7" />
        </template>
        <template v-if="item.badge" #suffix>
          <Badge :theme="item.badge.theme" :label="item.badge.label" variant="subtle" />
        </template>
      </SidebarItem>
    </SidebarSection>

    <template #footer>
      <SidebarCard v-if="!setup.canProvision" class="m-2">
        <p class="text-sm font-medium text-ink-gray-8">Finish setup</p>
        <p class="mt-1 text-p-sm text-ink-gray-6">
          {{ setup.blockers.length }} required
          {{ setup.blockers.length === 1 ? 'item' : 'items' }} left before you can
          provision.
        </p>
        <Button class="mt-2 w-full" label="Open setup" @click="$router.push('/setup')" />
      </SidebarCard>
    </template>
  </Sidebar>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useRoute } from 'vue-router'
import {
  Sidebar, SidebarHeader, SidebarSection, SidebarItem, SidebarCard,
  Avatar, Badge, Button, Icon,
} from '@/ui'
import { setup } from '../lib/setup'

const route = useRoute()
const collapsed = inject('sidebarCollapsed', false)

const nav = computed(() => [
  { to: '/tenants', label: 'Tenants', icon: 'lucide-users' },
  { to: '/jobs', label: 'Provisioning', icon: 'lucide-activity' },
  { to: '/shards', label: 'Shards', icon: 'lucide-server' },
  {
    to: '/setup',
    label: 'Setup',
    icon: 'lucide-settings',
    badge: setup.canProvision
      ? null
      : { theme: 'orange', label: String(setup.blockers.length) },
  },
])

// Nested routes should keep their section highlighted.
const isActive = (to) => route.path === to || route.path.startsWith(`${to}/`)
</script>

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
      <div class="p-2">
        <UserMenu
          :name="user.full_name"
          :email="user.email"
          subtitle="Operator"
          :extra="[
            { label: 'Settings', icon: 'lucide-settings', onClick: () => openSettings() },
          ]"
        />
      </div>

      <SidebarCard v-if="!setup.canProvision" class="m-2">
        <p class="text-sm font-medium text-ink-gray-8">Finish setup</p>
        <p class="mt-1 text-p-sm text-ink-gray-6">
          {{ setup.blockers.length }} required
          {{ setup.blockers.length === 1 ? 'item' : 'items' }} left before you can
          provision.
        </p>
        <Button class="mt-2 w-full" label="Open setup" @click="$router.push({ name: 'Setup' })" />
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
import UserMenu from './UserMenu.vue'
import { setup } from '../lib/setup'
import { openSettings } from '../lib/settings'
import { useResource } from '../lib/resource'

// Whoever is signed in. The desk is not part of the product, so this is the
// only place an operator sees their own account.
const userResource = useResource('frappe.client.get', {
  params: { doctype: 'User', name: 'me' },
  cacheKey: 'oneapp-admin-user',
  silent: true,
})
const user = computed(() => userResource.data || {})

const route = useRoute()
const collapsed = inject('sidebarCollapsed', false)

const nav = computed(() => [
  { to: '/admin/tenants', label: 'Tenants', icon: 'lucide-users' },
  { to: '/admin/jobs', label: 'Provisioning', icon: 'lucide-activity' },
  { to: '/admin/shards', label: 'Shards', icon: 'lucide-server' },
  {
    to: '/admin/setup',
    label: 'Readiness',
    icon: 'lucide-list-checks',
    badge: setup.canProvision
      ? null
      : { theme: 'orange', label: String(setup.blockers.length) },
  },
])

// Nested routes should keep their section highlighted.
const isActive = (to) => route.path === to || route.path.startsWith(`${to}/`)
</script>

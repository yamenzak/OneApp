<template>
  <Sidebar class="border-r border-outline-gray-1">
    <!-- Title and subtitle are props and the logo box is `#prefix`; SidebarHeader
         has no default slot, so hand-built header markup rendered nothing and
         left `title` unset, which the component then reads a first letter from. -->
    <SidebarHeader :title="ADMIN_APP" subtitle="Control plane">
      <template #prefix>
        <Avatar :label="ADMIN_APP" shape="square" size="lg" class="size-7" />
      </template>
    </SidebarHeader>

    <!-- SidebarItem is a full-width rounded row with no gutter of its own, so
         the active row's surface runs edge to edge unless the scroll region
         supplies one. frappe-ui's own sidebar stories put the nav in a
         ScrollArea with `viewport-class="px-2"`, which is also what gives the
         active row's shadow room instead of clipping it. -->
    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pt-0.5 pb-6">
      <nav class="flex flex-col gap-0.5">
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
            <Badge
              :theme="item.badge.theme"
              :label="item.badge.label"
              variant="subtle"
              class="mr-1"
            />
          </template>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <!-- Sidebar has one slot, the default: it hands the whole body to the app.
         A `#footer` template renders nothing at all, which is how the quota
         meter, the user menu and the setup card all silently disappeared.
         `mt-auto` is what pins this to the bottom of the flex column. -->
    <div class="mt-auto shrink-0">
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

      <!-- Title, body and button are props here too — SidebarCard has no default
           slot either, so the card showed as an empty bordered box. -->
      <SidebarCard
        v-if="!setup.canProvision"
        class="m-2"
        theme="amber"
        title="Finish setup"
        :description="`${setup.blockers.length} required ${
          setup.blockers.length === 1 ? 'item' : 'items'
        } left before you can provision.`"
        :action="{
          label: 'Open setup',
          onClick: () => $router.push({ name: 'Setup' }),
        }"
      />
    </div>
  </Sidebar>
</template>

<script setup>
import { ADMIN_APP } from '../lib/brand'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Sidebar, SidebarHeader, SidebarItem, SidebarCard,
  Avatar, Badge, Icon, ScrollArea,
} from '@/ui'
import UserMenu from './UserMenu.vue'
import { setup } from '../lib/setup'
import { openSettings } from '../lib/settings'
import { user } from '../lib/user'


const route = useRoute()

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
      : { theme: 'amber', label: String(setup.blockers.length) },
  },
])

// Nested routes should keep their section highlighted.
const isActive = (to) => route.path === to || route.path.startsWith(`${to}/`)
</script>

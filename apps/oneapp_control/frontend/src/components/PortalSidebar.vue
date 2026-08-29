<template>
  <Sidebar width="14rem" class="border-r border-outline-gray-1">
    <!-- No logo: the rail already shows the active workspace's avatar, and a
         header logo beside it would just say the same thing twice. -->
    <SidebarHeader
      :title="current?.tenant_name || 'Account'"
      :subtitle="current?.plan || ''"
      :show-logo="false"
    />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <SidebarItem
          v-for="item in nav"
          :key="item.label"
          :icon="item.icon"
          :to="item.to"
          :active="item.active"
        >
          <span class="flex-1 truncate text-sm">{{ item.label }}</span>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <!-- Sidebar has one slot, the default: it hands the whole body to the app.
         A `#footer` template renders nothing at all, which is how the quota
         meter, the user menu and the setup card all silently disappeared.
         `mt-auto` is what pins this to the bottom of the flex column. -->
    <div class="mt-auto shrink-0">
      <div class="p-2">
        <Button
          v-if="current?.url"
          class="mb-2 w-full"
          variant="subtle"
          label="Open workspace"
          icon-left="lucide-external-link"
          @click="openWorkspace"
        />
        <UserMenu :name="fullName" :email="email" :avatar="userImage" />
      </div>
    </div>
  </Sidebar>
</template>

<script setup>
import { computed } from 'vue'
import { Button, ScrollArea, Sidebar, SidebarHeader, SidebarItem } from '@/ui'
import UserMenu from './UserMenu.vue'
import { useNav } from '../lib/nav'
import { workspaces } from '../lib/customer'
import { fullName, email, userImage } from '../lib/user'

const current = computed(() => workspaces.selected)

// The destinations themselves live in lib/nav.js, so the sidebar here and the
// phone's bottom bar cannot name the same page two different things.
const nav = useNav()


const openWorkspace = () => window.open(current.value.url, '_blank', 'noopener')
</script>

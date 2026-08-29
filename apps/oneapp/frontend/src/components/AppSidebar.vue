<template>
  <Sidebar width="14rem" class="border-r border-outline-gray-1">
    <!-- No logo: the rail already shows the active app's tile, so a header logo
         beside it would say the same thing twice. -->
    <SidebarHeader
      :title="activeApp?.app_label || session.tenant?.name || TENANT_APP"
      :subtitle="activeApp ? session.tenant?.name : session.tenant?.plan"
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
        <QuotaMeter class="mb-2 px-1" />
      </div>
    </div>
  </Sidebar>
</template>

<script setup>
import { TENANT_APP } from '../lib/brand'
import { ScrollArea, Sidebar, SidebarHeader, SidebarItem } from '@/ui'
import QuotaMeter from './QuotaMeter.vue'
import { useNav } from '../lib/nav'
import { session } from '../lib/session'

// The destinations themselves live in lib/nav.js: the phone's bottom bar
// renders the same list, and two declarations of it drift into two different
// names for the same page. `activeApp` comes back with it because the header
// names whichever app the list belongs to.
const { nav, activeApp } = useNav()
</script>

<template>
  <Sidebar width="14rem" class="border-r border-outline-gray-1">
    <!-- No logo: the rail already shows the active space's tile, so a header
         logo beside it would say the same thing twice. -->
    <SidebarHeader
      :title="activeSpace?.space_label || session.tenant?.name || TENANT_APP"
      :subtitle="activeSpace ? session.tenant?.name : session.tenant?.plan"
      :show-logo="false"
    />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <template v-for="item in nav" :key="item.label">
          <SidebarItem :icon="item.icon" :to="item.to" :active="item.active">
            <span class="flex-1 truncate text-sm">{{ item.label }}</span>
            <!--
              The chevron is in `#suffix`, which frappe-ui renders as a sibling
              of the link rather than inside it — a button nested in an anchor
              is invalid, and the browser's own answer to it is to swallow one
              of the two clicks.
            -->
            <template v-if="expandable(item)" #suffix>
              <Button
                variant="ghost"
                :icon="open[item.key] ? 'lucide-chevron-down' : 'lucide-chevron-right'"
                :label="`Ways to see ${item.label}`"
                :tooltip="`Ways to see ${item.label}`"
                @click="toggle(item)"
              />
            </template>
          </SidebarItem>

          <div v-if="expandable(item) && open[item.key]" class="ms-3 border-s border-outline-gray-1 ps-1">
            <SidebarItem
              v-for="type in item.viewTypes"
              :key="type.key"
              :icon="type.icon"
              :to="type.to"
              :active="type.active"
            >
              <span class="flex-1 truncate text-sm">{{ type.label }}</span>
            </SidebarItem>
          </div>
        </template>
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
import { reactive, watch } from 'vue'
import { TENANT_APP } from '../lib/brand'
import { Button, ScrollArea, Sidebar, SidebarHeader, SidebarItem } from '@/ui'
import QuotaMeter from './QuotaMeter.vue'
import { useNav } from '../lib/nav'
import { session } from '../lib/session'

// The destinations themselves live in lib/nav.js: the phone's bottom bar
// renders the same list, and two declarations of it drift into two different
// names for the same page. `activeSpace` comes back with it because the header
// names whichever space the list belongs to.
const { nav, activeSpace } = useNav()

// Which screens are showing their view types. Not persisted: it is a glance,
// not a preference, and a sidebar that remembers what you opened last week is
// a sidebar you have to tidy.
const open = reactive({})

// Nothing to expand when a screen knows one way to be looked at — a chevron
// that opens a list of one is a control that lies about having a choice.
const expandable = (item) => (item.viewTypes || []).length > 1

const toggle = (item) => {
  open[item.key] = !open[item.key]
}

// The screen you are on opens itself, so arriving by any route — a link, a
// bookmark, the bottom bar — shows which way you are looking at it.
watch(
  nav,
  (items) => {
    for (const item of items) {
      if (item.active && expandable(item)) open[item.key] = true
    }
  },
  { immediate: true },
)
</script>

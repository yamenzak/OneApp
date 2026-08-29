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
          v-for="item in links"
          :key="item.label"
          :icon="item.icon"
          :to="item.to"
          :active="isActive(item)"
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ScrollArea, Sidebar, SidebarHeader, SidebarItem } from '@/ui'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { appIcon } from '../lib/icons'
import QuotaMeter from './QuotaMeter.vue'
import { session } from '../lib/session'

const route = useRoute()

const activeApp = computed(() =>
  session.apps.find((a) => a.app_code === route.params.appCode) || null,
)

// Sections come from the app's own manifest, so a new app brings its navigation
// with it rather than needing an edit here. Apps that declare none fall back to
// their landing page, which is what a single-screen app wants.
const appLinks = computed(() => {
  const app = activeApp.value
  if (!app) return []
  const declared = app.links || []
  if (!declared.length) {
    return [{
      label: app.app_label,
      icon: appIcon(app.icon),
      to: { name: 'App', params: { appCode: app.app_code } },
    }]
  }
  return declared.map((link) => ({
    label: link.label,
    icon: appIcon(link.icon),
    to: { name: 'App', params: { appCode: app.app_code }, query: { view: link.view } },
  }))
})

const workspaceLinks = [
  { label: 'Apps', icon: 'lucide-layout-grid', to: { name: 'Launcher' } },
  { label: 'Account', icon: 'lucide-circle-user', to: { name: 'Account' } },
]

const links = computed(() => (activeApp.value ? appLinks.value : workspaceLinks))

function isActive(item) {
  if (item.to.name !== route.name) return false
  if (item.to.query?.view) return route.query.view === item.to.query.view
  return true
}
</script>

<template>
  <!--
    The places a file can be, and how much room is left.

    Five entries, and every one of them is the same query with a different
    `where` — there is no second store behind any of them. That is why the rail
    is cheap and why a sixth would be a filter rather than a feature.

    The same `Sidebar` the space and mail rails are, and for the same reason
    they are the same: it is one column in one slot, and a plain div here meant
    the Drive alone had no header, no collapse and no resize handle — which
    read as a bug rather than as a decision, because it was one.
  -->
  <Sidebar
    v-model:collapsed="collapsed"
    :width="`${width}px`"
    class="border-r border-outline-gray-1"
  >
    <SidebarHeader title="Files" :subtitle="session.tenant?.name" :show-logo="false" />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <!-- The same component the space rail draws its screens with: a place
             in the Drive and a screen in a space are the same kind of thing to
             a reader, and two components would be two shapes for one idea. -->
        <SidebarItem
          v-for="entry in PLACES"
          :key="entry.value"
          data-slot="drive-place"
          :icon="entry.icon"
          :to="{ name: 'Drive', query: { place: entry.value } }"
          :active="entry.value === place"
        >
          <span class="flex-1 truncate text-sm">{{ entry.label }}</span>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <div class="mt-auto shrink-0">
      <div class="p-2">
        <!-- The quota was enforced at upload time and shown nowhere, which is
             the worst of both: a refusal with no way to have seen it coming.
             Hidden while collapsed for the same reason the space rail's meter
             is — a label and a bar do not survive 3rem of width. -->
        <UsageBar
          v-if="storage?.workspace && !collapsed"
          label="Storage"
          :usage="storage.workspace"
          format="bytes"
          class="mb-2 px-1"
        />
        <SidebarCollapseToggle />
      </div>
    </div>
  </Sidebar>

  <Resizer
    v-if="!collapsed"
    v-model="width"
    :min="MIN"
    :default-size="DEFAULT"
    :max="MAX"
    side="right"
    label="the sidebar"
    remember="onespace.sidebar"
    slot-name="sidebar-resizer"
  />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
} from '@/ui'
import Resizer from '../Resizer.vue'
import UsageBar from '../UsageBar.vue'
import { PLACES } from './places'
import { workspace } from '../../lib/workspace'
import { session } from '../../lib/session'
import { DEFAULT, MAX, MIN, useSidebar } from '../../lib/sidebar'

defineProps({
  place: { type: String, default: 'home' },
})

const { collapsed, width } = useSidebar()

// Fetched here rather than passed in, because this is the only thing that
// draws it — the shell has no business knowing what the Drive's rail shows.
const storage = ref(null)
onMounted(async () => {
  storage.value = await workspace.driveStorage().catch(() => null)
})
</script>

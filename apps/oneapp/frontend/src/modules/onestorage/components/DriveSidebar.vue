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
    class="border-e border-outline-gray-1"
  >
    <!-- No header. The bar's corner names the workspace directly above this and
         the trail beside it names where you are, so a header here was a third
         telling of the same two words — and its own dropdown, which read as a
         second switcher. -->

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

      <!--
        Folders on other people's servers, under a heading of their own.

        Below the places and not among them, because they are not places: a
        place is a `where` on one table and these are sockets. The heading is
        what says so, and the dot beside each says whether the host answered
        the last time anybody asked.
      -->
      <nav v-if="mounts.length" class="mt-4 space-y-0.5">
        <p
          v-if="!collapsed"
          data-slot="drive-mounts-heading"
          class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5"
        >
          {{ __('Connected') }}
        </p>
        <SidebarItem
          v-for="one in mounts"
          :key="one.name"
          data-slot="drive-mount"
          icon="lucide-server"
          :to="{ name: 'Drive', query: { place: 'home', folder: `remote://${one.name}/` } }"
          :active="one.name === mount"
        >
          <span class="flex-1 truncate text-sm">{{ one.folder_name }}</span>
          <!-- Two marks and no third. A mount that is working needs none —
               a green dot beside every one of them is a rail that looks like
               a status page — and the two that are worth distinguishing are
               "off because somebody said so" and "off because it broke". -->
          <span
            v-if="one.status !== 'Connected'"
            class="me-0.5 size-1.5 shrink-0 rounded-full"
            :class="one.status === 'Failing' ? 'bg-surface-red-5' : 'bg-surface-gray-4'"
            :aria-label="one.status === 'Failing' ? __('Not answering') : __('Paused')"
          />
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
          :label="__('Storage')"
          :usage="storage.workspace"
          format="bytes"
          class="mb-2 px-1"
        />
      </div>
      <ShellFoot />
    </div>
  </Sidebar>

  <SidebarResizer />
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  ScrollArea,
  Sidebar,
  SidebarItem,
} from '@/ui'
import ShellFoot from '@/modules/onespace/components/shell/ShellFoot.vue'
import SidebarResizer from '@/modules/onespace/components/SidebarResizer.vue'
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import { PLACES } from '@/modules/onestorage/components/places'
import { mountOf } from '@/modules/onestorage/lib/files'
import { workspace } from '@/shared/lib/workspace'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  place: { type: String, default: 'home' },
  // Which folder the page is looking at, so a mount can mark itself. A
  // `remote://` name carries its own mount and nothing else does.
  folder: { type: String, default: '' },
})

const mount = computed(() => mountOf(props.folder))

const { collapsed, width } = useSidebar()

// Fetched here rather than passed in, because this is the only thing that
// draws it — the shell has no business knowing what the Drive's rail shows.
const storage = ref(null)
// The mounts a person may browse. Empty on every workspace that has never
// connected one, which is most of them — and an empty list draws nothing, so
// the rail is unchanged until somebody uses the feature.
const mounts = ref([])
onMounted(async () => {
  storage.value = await workspace.driveStorage().catch(() => null)
  mounts.value = (await workspace.driveMounts().catch(() => null)) || []
})
</script>

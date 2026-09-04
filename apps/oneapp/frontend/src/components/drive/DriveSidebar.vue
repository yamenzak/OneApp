<!--
  The places a file can be, and how much room is left.

  Five entries, and every one of them is the same query with a different `where`
  — there is no second store behind any of them. That is why the rail is cheap
  and why a sixth would be a filter rather than a feature.
-->
<template>
  <div class="flex h-full flex-col">
    <div class="flex-1 overflow-y-auto p-2">
      <p class="px-2 pb-2 pt-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
        Files
      </p>

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
    </div>

    <!-- The quota was enforced at upload time and shown nowhere, which is the
         worst of both: a refusal with no way to have seen it coming. -->
    <div v-if="storage?.workspace" class="border-t border-outline-gray-1 p-3">
      <UsageBar label="Storage" :usage="storage.workspace" format="bytes" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { SidebarItem } from '@/ui'
import UsageBar from '../UsageBar.vue'
import { workspace } from '../../lib/workspace'

const PLACES = [
  { value: 'home', label: 'All files', icon: 'lucide-folder' },
  { value: 'recents', label: 'Recent', icon: 'lucide-clock' },
  { value: 'favourites', label: 'Favourites', icon: 'lucide-heart' },
  { value: 'shared', label: 'Shared with me', icon: 'lucide-users' },
  { value: 'trash', label: 'Bin', icon: 'lucide-trash-2' },
]

defineProps({
  place: { type: String, default: 'home' },
})

// Fetched here rather than passed in, because this is the only thing that
// draws it — the shell has no business knowing what the Drive's rail shows.
const storage = ref(null)
onMounted(async () => {
  storage.value = await workspace.driveStorage().catch(() => null)
})

</script>

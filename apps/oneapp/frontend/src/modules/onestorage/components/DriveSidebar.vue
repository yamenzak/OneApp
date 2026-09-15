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
        <!-- A link on the page and a press in a window: a window has no
             address of its own to link into, and following one would take the
             page underneath somewhere. `docs/DESKTOP.md` stage 6. -->
        <SidebarItem
          v-for="entry in PLACES"
          :key="entry.value"
          data-slot="drive-place"
          :icon="entry.icon"
          :to="windowed ? undefined : { name: 'Drive', query: { place: entry.value } }"
          :active="entry.value === place"
          @click="windowed && emit('go', { place: entry.value, folder: '' })"
        >
          <span class="flex-1 truncate text-sm">{{ entry.label }}</span>
        </SidebarItem>
      </nav>

      <!--
        The drive's own shape, under the places.

        Below them and not among them for the same reason the mounts are: a
        place is a fixed `where` and a folder is one you made. Collapsed by
        default and fetched a level at a time — see `FolderTree`.
      -->
      <nav v-if="!collapsed && roots.length" class="mt-4 space-y-0.5">
        <p
          data-slot="drive-folders-heading"
          class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-muted"
        >
          {{ __('Folders') }}
        </p>
        <FolderTree
          :nodes="roots"
          :folder="folder"
          :windowed="windowed"
          @go="emit('go', $event)"
        />
      </nav>

      <!--
        Folders on other people's servers, under a heading of their own.

        Below the places and not among them, because they are not places: a
        place is a `where` on one table and these are sockets. The heading is
        what says so, and the dot beside each says whether the host answered
        the last time anybody asked.

        The glyph says which kind of socket. One `lucide-server` on all five
        said only "somewhere else", which the heading above them already says —
        and an SFTP box, an office share and a NAS are three different things
        to think about. `iconForProtocol` holds the map, including the one pair
        worth telling apart hardest: FTPS and plain FTP, a closed lock and an
        open one.
      -->
      <nav v-if="mounts.length" class="mt-4 space-y-0.5">
        <p
          v-if="!collapsed"
          data-slot="drive-mounts-heading"
          class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-muted"
        >
          {{ __('Connected') }}
        </p>
        <SidebarItem
          v-for="one in mounts"
          :key="one.name"
          data-slot="drive-mount"
          :icon="iconForProtocol(one.protocol)"
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
      <!-- Whose workspace this is, and the bell. The shell's foot, drawn at
           the foot of the shell's column — and not inside a window, where the
           shell is six feet away down the left-hand side and a second copy of
           it is a second answer to "who am I signed in as". -->
      <ShellFoot v-if="!windowed" />
    </div>
  </Sidebar>

  <!-- The handle belongs to the shell's column. A window is resized by its own
       corner, and a rail inside one is as wide as the window lets it be. -->
  <SidebarResizer v-if="!windowed" />
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
import FolderTree from '@/modules/onestorage/components/FolderTree.vue'
import { iconForProtocol, mountOf } from '@/modules/onestorage/lib/files'
import { workspace } from '@/shared/lib/workspace'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  place: { type: String, default: 'home' },
  // Which folder the page is looking at, so a mount can mark itself. A
  // `remote://` name carries its own mount and nothing else does.
  folder: { type: String, default: '' },
  /** Drawn inside OneCloud's window rather than in the shell's sidebar. */
  windowed: { type: Boolean, default: false },
})

const emit = defineEmits(['go'])

const mount = computed(() => mountOf(props.folder))

const { collapsed, width } = useSidebar()

// Fetched here rather than passed in, because this is the only thing that
// draws it — the shell has no business knowing what the Drive's rail shows.
const storage = ref(null)
// The mounts a person may browse. Empty on every workspace that has never
// connected one, which is most of them — and an empty list draws nothing, so
// the rail is unchanged until somebody uses the feature.
const mounts = ref([])

// The top of the tree. One call, and the levels under it are fetched only when
// somebody opens them — a rail that mapped the whole drive on every page load
// would cost more than the list it sits beside.
const roots = ref([])

onMounted(async () => {
  storage.value = await workspace.driveStorage().catch(() => null)
  mounts.value = (await workspace.driveMounts().catch(() => null)) || []
  const found = await workspace.driveFolders('').catch(() => null)
  roots.value = found?.files || []
})
</script>

<template>
  <!--
    The places a file can be, and how much room is left.

    Four bands, not a list: where your files are, the record tree, your own
    folders and anything mounted, and the bin at the foot. Every place in it is
    the same query with a different `where` — there is no second store behind
    any of them, which is why the rail is cheap and why the discipline has to
    come from somewhere else. It comes from `places.js`: a place is a question
    the endpoint answers, a rail entry is a claim that you go there often, and
    keeping those two lists apart is what stopped this column growing an entry
    per filter.

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
      <!-- The bands, out of `places.js`. Ten flat entries became five and a
           tree: Documents, Workbooks and Code were the same filter as three of
           the kind pills an inch to the right, and Templates is something you
           pick from the New menu rather than a room you go and stand in. All
           four are still places the endpoint answers, so the links keep
           working; none of them is worth a permanent seat. -->
      <nav
        v-for="(band, index) in RAIL"
        :key="band.key"
        class="space-y-0.5"
        :class="index ? 'mt-4' : ''"
      >
        <!-- The same component the space rail draws its screens with: a place
             in the Drive and a screen in a space are the same kind of thing to
             a reader, and two components would be two shapes for one idea. -->
        <!-- A link on the page and a press in a window: a window has no
             address of its own to link into, and following one would take the
             page underneath somewhere. `docs/DESKTOP.md` stage 6. -->
        <SidebarItem
          v-for="entry in band.places"
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
          :nodes="shownRoots"
          :folder="folder"
          :windowed="windowed"
          @go="emit('go', $event)"
        />
        <!--
          A rail is a shortcut, not a map.

          It drew every root folder, and a workspace with fifty of them got
          fifty — a column of truncated names taller than the window, with the
          places it exists for scrolled off the top. Six, and the rest are one
          press away; All files is the map and is the first entry in the rail.
        -->
        <Button
          v-if="roots.length > FEW"
          variant="ghost"
          size="sm"
          class="w-full !justify-start !px-2 !text-ink-muted"
          data-slot="drive-folders-more"
          :label="allRoots
            ? __('Show fewer')
            : __('{0} more', [roots.length - FEW])"
          @click="allRoots = !allRoots"
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
      <!-- The bin, at the bottom, where every file manager anybody has used
           puts it. It was seventh of ten in a flat list, between Code and
           Records, which is nowhere. -->
      <nav class="px-2 pb-1">
        <SidebarItem
          data-slot="drive-place"
          :icon="BIN.icon"
          :to="windowed ? undefined : { name: 'Drive', query: { place: BIN.value } }"
          :active="BIN.value === place"
          @click="windowed && emit('go', { place: BIN.value, folder: '' })"
        >
          <span class="flex-1 truncate text-sm">{{ BIN.label }}</span>
        </SidebarItem>
      </nav>
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
  Button,
  ScrollArea,
  Sidebar,
  SidebarItem,
} from '@/ui'
import ShellFoot from '@/modules/onespace/components/shell/ShellFoot.vue'
import SidebarResizer from '@/modules/onespace/components/SidebarResizer.vue'
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import { BIN, RAIL } from '@/modules/onestorage/components/places'
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

/** How many of them the rail draws before it stops being a rail. */
const FEW = 6
const allRoots = ref(false)
const shownRoots = computed(() => (
  allRoots.value ? roots.value : roots.value.slice(0, FEW)
))

onMounted(async () => {
  storage.value = await workspace.driveStorage().catch(() => null)
  mounts.value = (await workspace.driveMounts().catch(() => null)) || []
  const found = await workspace.driveFolders('').catch(() => null)
  roots.value = found?.files || []
})
</script>

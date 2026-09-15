<!--
  The shape of the drive, one level at a time.

  A place in the rail above is a `where` on the File table; a folder is a
  `where` too, so this is the same query again and not a second store — the
  rule the whole of `onestorage` is built on. What it adds is nesting: you can
  see that a folder has folders in it without walking into it first, which is
  the one thing a flat list of places cannot say.

  **One level per call.** Children arrive the first time a folder is opened and
  are kept after that. Fetching the whole shape of a drive to draw three rows
  would make the rail slower than the list beside it, and most folders are
  never opened.

  **The chevron is a sibling of the link, not inside it.** `SidebarItem`'s
  `suffix` slot exists for exactly this: a button inside a link is invalid and
  unreachable by a keyboard. So the name navigates and the chevron discloses,
  which is also how a person expects each to behave.

  It recurses through itself, which is the one honest way to draw a tree.
-->
<template>
  <div :class="depth ? 'ps-3' : ''">
    <template v-for="node in nodes" :key="node.name">
      <!-- A link on the page, a press in a window — see `DriveSidebar`. -->
      <SidebarItem
        data-slot="drive-folder"
        icon="lucide-folder"
        :to="windowed ? undefined : { name: 'Drive', query: { place: 'home', folder: node.name } }"
        :active="node.name === folder"
        @click="windowed && emit('go', { place: 'home', folder: node.name })"
      >
        <span class="flex-1 truncate text-sm">{{ node.file_name }}</span>
        <template #suffix>
          <!--
            Drawn for every folder, because whether one has folders in it is
            not known until it is asked — and a chevron that appears after the
            answer arrives is a control that moves under the pointer.
          -->
          <Button
            variant="ghost"
            size="sm"
            :icon="open.has(node.name) ? 'lucide-chevron-down' : 'lucide-chevron-right'"
            :label="open.has(node.name)
              ? __('Collapse {0}', [node.file_name])
              : __('Expand {0}', [node.file_name])"
            :tooltip="open.has(node.name) ? __('Collapse') : __('Expand')"
            :loading="loading.has(node.name)"
            @click.stop.prevent="toggle(node)"
          />
        </template>
      </SidebarItem>

      <!--
        An opened folder with nothing in it says so rather than collapsing
        back, which reads as a control that did not work.
      -->
      <FolderTree
        v-if="open.has(node.name) && children[node.name]?.length"
        :nodes="children[node.name]"
        :folder="folder"
        :depth="depth + 1"
        :windowed="windowed"
        @go="emit('go', $event)"
      />
      <p
        v-else-if="open.has(node.name) && children[node.name]"
        class="ps-8 pb-1 text-xs text-ink-muted"
      >
        {{ __('No folders in here') }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Button, SidebarItem } from '@/ui'
// Itself, by name. A Vue SFC may recurse without this — the filename is the
// component name — and `test_every_component_a_template_uses_is_one_the_script_imported`
// is right to refuse it anyway: a reader looking for where `<FolderTree>` comes
// from should find an answer in the script, and the one honest answer here is
// "this file".
import FolderTree from '@/modules/onestorage/components/FolderTree.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

defineOptions({ name: 'FolderTree' })

defineProps({
  /** This level's folders, already fetched by whoever drew it. */
  nodes: { type: Array, default: () => [] },
  /** Which folder the list beside this is showing, so the rail can mark it. */
  folder: { type: String, default: '' },
  /** How deep this level is, which is all the indent needs to know. */
  depth: { type: Number, default: 0 },
  /** Drawn inside OneCloud's window, where a folder is pressed rather than
   *  linked to. Passed down each level, because a tree recurses. */
  windowed: { type: Boolean, default: false },
})

const emit = defineEmits(['go'])

const open = ref(new Set())
const loading = ref(new Set())
// Keyed by folder name: absent means never asked, `[]` means asked and empty.
const children = reactive({})

async function toggle(node) {
  if (open.value.has(node.name)) {
    open.value.delete(node.name)
    open.value = new Set(open.value)
    return
  }

  open.value = new Set(open.value).add(node.name)
  if (children[node.name]) return

  loading.value = new Set(loading.value).add(node.name)
  try {
    const found = await workspace.driveFolders(node.name)
    children[node.name] = found?.files || []
  } catch {
    // A folder that could not be read closes again rather than sitting open
    // over nothing: the rail is not the place to explain a failed request,
    // and the list says so when you walk into it.
    open.value = new Set([...open.value].filter((one) => one !== node.name))
  } finally {
    const next = new Set(loading.value)
    next.delete(node.name)
    loading.value = next
  }
}
</script>

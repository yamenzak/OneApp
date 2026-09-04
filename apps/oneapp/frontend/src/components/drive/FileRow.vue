<!--
  One file, as a row or as a card.

  The same component draws both, because a list and a grid of the same files
  differ in layout and not in what a file *is* — two components would be two
  places to add a column to.

  The row is a container and not itself the control. Opening a file and hearting
  it are different actions on the same line, and a button inside a button is
  neither valid nor reachable by a keyboard — which is what this was before the
  heart and the menu arrived.

  Those controls are always drawn rather than revealed on hover. A phone has no
  hover, so a heart that appears on `group-hover` is a heart that does not exist
  on half the devices this runs on.
-->
<template>
  <div
    data-slot="drive-file"
    :data-kind="file.custom_kind || 'Other'"
    :data-selected="selected ? 'true' : undefined"
    :class="[
      grid
        ? 'flex flex-col gap-2 rounded-6 border border-outline-gray-1 p-3'
        : 'flex items-center gap-2 rounded-4 pr-2',
      selected ? 'bg-surface-gray-2' : 'hover:bg-surface-gray-2',
    ]"
  >
    <!--
      Selection is opt-in per surface: the picker offers one file and a
      checkbox there would be a control that does nothing.
    -->
    <!--
      `aria-label` and not `label`: frappe-ui's Checkbox renders a label as
      visible text, and forty rows each captioned "Select Perspective.jpg" is a
      column of instructions where a column of checkboxes belongs. The name is
      still announced, which is the part that mattered.
    -->
    <Checkbox
      v-if="selectable"
      :model-value="selected"
      :aria-label="`Select ${file.file_name}`"
      class="ml-2.5 shrink-0"
      @update:model-value="emit('select', file)"
    />

    <!--
      A folder is a link and a file is a button. A folder is a place with a URL
      — which is the whole reason the folder is in the query string — so the
      browser's own middle-click, copy-link and back button all work without a
      line of ours. A file is not a place; opening one is an action.
    -->
    <router-link
      v-if="file.is_folder"
      data-slot="drive-open"
      class="flex min-w-0 flex-1 rounded-4 px-2 py-2"
      :class="grid ? '!px-0 !py-0' : ''"
      :to="{ name: 'Drive', query: { place: 'home', folder: file.name } }"
    >
      <FileFace :file="file" :grid="grid" />
    </router-link>

    <Button
      v-else
      data-slot="drive-open"
      variant="ghost"
      :label="file.file_name"
      class="!h-auto min-w-0 flex-1 !justify-start !px-2 !py-2"
      :class="grid ? '!px-0 !py-0' : ''"
      @click="emit('open', file)"
    >
      <FileFace :file="file" :grid="grid" />
    </Button>

    <div
      class="flex shrink-0 items-center gap-1"
      :class="grid ? 'justify-between' : ''"
    >
      <!-- The heart is the whole of Favourites: `_liked_by` on the row, which
           the framework keeps on every doctype. So the rail's Favourites is a
           filter over one column and not a table. -->
      <Button
        v-if="actions"
        icon="lucide-heart"
        variant="ghost"
        :class="file.liked ? 'text-ink-red-3' : 'text-ink-gray-4'"
        :label="file.liked ? `Remove ${file.file_name} from favourites` : `Add ${file.file_name} to favourites`"
        :tooltip="file.liked ? 'Remove from favourites' : 'Add to favourites'"
        @click="emit('favourite', file)"
      />

      <template v-if="!grid">
        <Avatar
          v-if="file.owner_person?.label"
          size="sm"
          :label="file.owner_person.label"
          :image="file.owner_person.image"
        />
        <span class="w-24 shrink-0 text-p-xs text-ink-gray-5">{{ when }}</span>
      </template>

      <Dropdown v-if="menu.length" :options="menu" align="end">
        <Button
          data-slot="drive-more"
          icon="lucide-ellipsis-vertical"
          variant="ghost"
          :label="`More for ${file.file_name}`"
          tooltip="More"
        />
      </Dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar, Button, Checkbox, Dropdown, dayjsLocal } from '@/ui'
import FileFace from './FileFace.vue'

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
  // Off in the picker, which offers one file and has nothing to do in bulk.
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  // Off in the picker too: the heart and the menu are the Drive's, and a
  // rename control behind an Attach field is a control in the wrong place.
  actions: { type: Boolean, default: false },
  // What the bin offers instead, because everything else there is a no-op.
  trashed: { type: Boolean, default: false },
  canWrite: { type: Boolean, default: true },
})

const emit = defineEmits([
  'open', 'select', 'favourite', 'share', 'rename', 'move', 'trash', 'restore', 'destroy',
])

const menu = computed(() => {
  if (!props.actions) return []
  if (props.trashed) {
    return [
      { label: 'Put it back', icon: 'lucide-rotate-ccw', onClick: () => emit('restore', props.file) },
      { label: 'Delete for good', icon: 'lucide-trash-2', onClick: () => emit('destroy', props.file) },
    ]
  }
  const items = [{ label: 'Share', icon: 'lucide-user-plus', onClick: () => emit('share', props.file) }]
  if (props.canWrite) {
    items.push(
      { label: 'Rename', icon: 'lucide-pencil', onClick: () => emit('rename', props.file) },
      { label: 'Move to a folder', icon: 'lucide-folder-input', onClick: () => emit('move', props.file) },
      { label: 'Move to the bin', icon: 'lucide-trash-2', onClick: () => emit('trash', props.file) },
    )
  }
  return items
})

const when = computed(() =>
  props.file.modified ? dayjsLocal(props.file.modified).fromNow() : '',
)

</script>

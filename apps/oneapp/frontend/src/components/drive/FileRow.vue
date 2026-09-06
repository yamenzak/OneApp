<!--
  One file, as a row or as a card. The same component draws both, because a list
  and a grid of the same files differ in layout and not in what a file *is*.

  The row is a container and not itself the control: opening a file and hearting
  it are different actions on the same line, and a button inside a button is
  neither valid nor reachable by a keyboard. Those controls are always drawn
  rather than revealed on hover — a phone has no hover.
-->
<template>
  <div
    data-slot="drive-file"
    :data-kind="file.custom_kind || 'Other'"
    :data-selected="selected ? 'true' : undefined"
    :draggable="movable"
    :class="[
      grid
        ? 'flex flex-col gap-2 rounded-6 border border-outline-gray-1 p-3'
        : 'flex items-center gap-2 rounded-4 pe-2',
      selected ? 'bg-surface-gray-2' : 'hover:bg-surface-gray-2',
      over ? 'ring-2 ring-outline-gray-3' : '',
      lifted ? 'opacity-50' : '',
    ]"
    @contextmenu="emit('menu', menu)"
    @dragstart="onDragStart"
    @dragend="lifted = false"
    @dragover="onDragOver"
    @dragleave="over = false"
    @drop="onDrop"
  >
    <!-- Selection is opt-in per surface: the picker offers one file, and a
         checkbox there would do nothing. -->
    <!-- `aria-label` and not `label`: frappe-ui's Checkbox renders a label as
         visible text, and forty rows captioned "Select Perspective.jpg" is a
         column of instructions. -->
    <Checkbox
      v-if="selectable"
      :model-value="selected"
      :aria-label="__('Select {0}', [file.file_name])"
      class="ms-2.5 shrink-0"
      @update:model-value="emit('select', file)"
    />

    <!--
      Anything with an address is a link; everything else is a button.

      A folder always was: it is a place, so middle-click, copy-link and the
      back button work without a line of ours. What changed is that a sheet, a
      document and a text file are places too now — `routeFor` gives each one a
      URL — and while they were buttons the only way to keep a quotation open
      while pricing it was a window manager we would have had to write. A
      cmd-click is that window manager, and every browser already ships it.

      A `.zip` is still not a place. Opening one is an action, and it stays a
      button.
    -->
    <router-link
      v-if="file.is_folder || link"
      data-slot="drive-open"
      class="flex min-w-0 flex-1 rounded-4 px-2 py-2"
      :class="grid ? '!px-0 !py-0' : ''"
      :to="file.is_folder
        ? { name: 'Drive', query: { place: 'home', folder: file.name } }
        : link"
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
           the framework keeps on every doctype. -->
      <Button
        v-if="actions"
        icon="lucide-heart"
        variant="ghost"
        :class="file.liked ? 'text-ink-red-3' : 'text-ink-gray-4'"
        :label="
          file.liked
            ? __('Remove {0} from favourites', [file.file_name])
            : __('Add {0} to favourites', [file.file_name])
        "
        :tooltip="file.liked ? __('Remove from favourites') : __('Add to favourites')"
        @click="emit('favourite', file)"
      />

      <!-- Who and when, on a screen with room for them. On a phone they are the
           first two things to go. -->
      <template v-if="!grid">
        <Avatar
          v-if="file.owner_person?.label"
          class="hidden sm:flex"
          size="sm"
          :label="file.owner_person.label"
          :image="file.owner_person.image"
        />
        <span class="hidden w-24 shrink-0 text-p-xs text-ink-gray-5 sm:block">
          {{ when }}
        </span>
      </template>

      <Dropdown v-if="menu.length" :options="menu" align="end">
        <Button
          data-slot="drive-more"
          icon="lucide-ellipsis-vertical"
          variant="ghost"
          :label="__('More for {0}', [file.file_name])"
          :tooltip="__('More')"
        />
      </Dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Avatar, Button, Checkbox, Dropdown, dayjsLocal } from '@/ui'
import FileFace from './FileFace.vue'
import { __ } from '@/lib/runtime/translate'

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
  // Off in the picker, which offers one file and has nothing to do in bulk.
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  // Off in the picker too: a rename control behind an Attach field is a control
  // in the wrong place.
  actions: { type: Boolean, default: false },
  /**
   * Where clicking this file goes, when it goes anywhere: a route location
   * from `routeFor`, or null for a file that is looked at rather than opened.
   *
   * Passed rather than computed here because the caller is the one that knows
   * what to come back to — a record's Files tab sends the record along so the
   * editor's trail leads home.
   */
  link: { type: Object, default: null },
  // What the bin offers instead, because everything else there is a no-op.
  trashed: { type: Boolean, default: false },
  canWrite: { type: Boolean, default: true },
  // Dragging is the Drive's alone: in the picker there is nowhere to drag to.
  movable: { type: Boolean, default: false },
})

const emit = defineEmits([
  'open', 'select', 'favourite', 'share', 'rename', 'move', 'trash', 'restore',
  'destroy', 'menu', 'move-into',
])

const menu = computed(() => {
  if (!props.actions) return []
  if (props.trashed) {
    return [
      { label: __('Put it back'), icon: 'lucide-rotate-ccw', onClick: () => emit('restore', props.file) },
      { label: __('Delete for good'), icon: 'lucide-trash-2', onClick: () => emit('destroy', props.file) },
    ]
  }
  const items = [{ label: __('Share'), icon: 'lucide-user-plus', onClick: () => emit('share', props.file) }]
  if (props.canWrite) {
    items.push(
      { label: __('Rename'), icon: 'lucide-pencil', onClick: () => emit('rename', props.file) },
      { label: __('Move to a folder'), icon: 'lucide-folder-input', onClick: () => emit('move', props.file) },
      { label: __('Move to the bin'), icon: 'lucide-trash-2', onClick: () => emit('trash', props.file) },
    )
  }
  return items
})

const when = computed(() =>
  props.file.modified ? dayjsLocal(props.file.modified).fromNow() : '',
)

// --- dragging a row onto a folder -------------------------------------------

// Our own MIME type, and not `text/plain`: a row dragged into a text field
// would otherwise paste a row id, and a file dragged in from the desktop would
// look to us like one of ours.
const MOVING = 'application/x-onespace-file'

const lifted = ref(false)
const over = ref(false)

function onDragStart(event) {
  if (!props.movable) return
  lifted.value = true
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData(MOVING, props.file.name)
}

function onDragOver(event) {
  // Only a folder is a destination, and only for one of ours. A file dragged
  // from the desktop falls through to the page's own drop zone, which uploads
  // it.
  if (!props.file.is_folder || !event.dataTransfer.types.includes(MOVING)) return
  event.preventDefault()
  event.stopPropagation()
  event.dataTransfer.dropEffect = 'move'
  over.value = true
}

function onDrop(event) {
  over.value = false
  if (!props.file.is_folder) return
  const moving = event.dataTransfer.getData(MOVING)
  if (!moving || moving === props.file.name) return
  event.preventDefault()
  event.stopPropagation()
  emit('move-into', props.file, [moving])
}

</script>

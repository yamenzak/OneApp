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
      rowState({ selected, drop: over, lifted }),
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
      v-if="selectable && !remote"
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
    <!--
      `inline` is the host saying it will open this one itself.

      The link stays a link — that is what makes cmd-click open a tab, and a
      file manager where a modifier does nothing is a file manager somebody
      fights. What changes is the plain click: the Drive opens a sheet in the
      pane beside the list rather than walking away from the list, so it takes
      the click and the anchor keeps every other way of using it.
    -->
    <router-link
      v-if="file.is_folder || link"
      data-slot="drive-open"
      class="flex min-w-0 flex-1 rounded-4 px-2 py-2"
      :class="grid ? '!px-0 !py-0' : ''"
      :to="file.is_folder
        ? { name: 'Drive', query: { place: 'home', folder: file.name } }
        : link"
      @click.capture="onOpen"
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
        v-if="actions && !remote"
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
          v-if="file.owner_person?.label && !dense"
          class="hidden md:flex"
          size="sm"
          :label="file.owner_person.label"
          :image="file.owner_person.image"
        />
        <!-- The same words the face already says under the name — "Folder ·
             9 days ago" — so in a narrow list it is the column to lose, not
             the name. -->
        <span
          v-if="!dense"
          class="hidden w-24 shrink-0 text-p-xs text-ink-muted md:block"
        >
          {{ when }}
        </span>
      </template>

      <!-- The same menu a record's row has, in the same place, revealed the
           same way — `shared/components/RowMenu.vue`. -->
      <RowMenu
        v-if="menu.length"
        :items="menu"
        :label="__('What to do with {0}', [file.file_name])"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Avatar, Button, Checkbox } from '@/ui'
import RowMenu from '@/shared/components/RowMenu.vue'
import FileFace from '@/modules/onestorage/components/FileFace.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'
import { rowState } from '@/shared/lib/rowstate'

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
  /**
   * The kinds this host opens itself rather than navigating to.
   *
   * The Drive passes Sheet and Doc: those open in the pane beside the list.
   * Everywhere else this is empty and a link is a link.
   */
  inline: { type: Array, default: () => [] },
  /**
   * The list is sharing its width with something — the Drive's pane, open on a
   * file. A viewport breakpoint cannot see that: the window is still wide and
   * only this column is narrow, so who-and-when goes on a word from the host
   * rather than on `sm:`. The name is what a list is for; the avatar is not.
   */
  dense: { type: Boolean, default: false },
})

/**
 * A plain click on a kind the host claims, handed to the host.
 *
 * Every modifier is left alone — cmd, ctrl, shift, middle-click and the
 * context menu all belong to the anchor, and taking them would be taking the
 * only ways to open a second one.
 *
 * On the capture phase, which is the whole reason this works. `RouterLink`
 * binds its own click handler inside its render, so a plain `@click` here is a
 * fallthrough listener that runs *after* it — the navigation has already been
 * decided by the time `preventDefault` is called, and the page changes anyway.
 * A capture listener on the same element runs before every bubble one.
 */
function onOpen(event) {
  if (props.file.is_folder) return
  if (!props.inline.includes(props.file.custom_kind)) return
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return
  event.preventDefault()
  emit('open', props.file)
}

const emit = defineEmits([
  'open', 'select', 'favourite', 'share', 'rename', 'move', 'trash', 'restore',
  'destroy', 'menu', 'move-into', 'copy',
])

/**
 * A file on a mounted host, which is not a row here at all.
 *
 * Nothing that writes is offered on one: there is no `File` to rename, no
 * `_liked_by` to heart and no `DocShare` to hang a share on. The server
 * refuses all three with a sentence rather than a stack trace — see
 * `remote.deny` — and this is the half that stops anybody reaching them.
 */
const remote = computed(() => !!props.file.remote)

const menu = computed(() => {
  if (!props.actions) return []
  if (remote.value) {
    // One thing, and it is the seam: bringing the file across is what makes
    // every other item on this menu possible.
    return props.file.is_folder
      ? []
      : [{
        label: __('Copy into the Drive'),
        icon: 'lucide-download',
        onClick: () => emit('copy', props.file),
      }]
  }
  if (props.trashed) {
    return [
      { label: __('Put it back'), icon: 'lucide-rotate-ccw', onClick: () => emit('restore', props.file) },
      { label: __('Delete for ever'), icon: 'lucide-trash-2', theme: 'red', onClick: () => emit('destroy', props.file) },
    ]
  }
  const items = [{ label: __('Share'), icon: 'lucide-user-plus', onClick: () => emit('share', props.file) }]
  if (props.canWrite) {
    items.push(
      { label: __('Rename'), icon: 'lucide-pencil', onClick: () => emit('rename', props.file) },
      { label: __('Move to a folder'), icon: 'lucide-folder-input', onClick: () => emit('move', props.file) },
      { label: __('Move to the bin'), icon: 'lucide-trash-2', theme: 'red', onClick: () => emit('trash', props.file) },
    )
  }
  return items
})

const when = computed(() =>
  props.file.modified ? ago(props.file.modified) : '',
)

// --- dragging a row onto a folder -------------------------------------------

// Our own MIME type, and not `text/plain`: a row dragged into a text field
// would otherwise paste a row id, and a file dragged in from the desktop would
// look to us like one of ours.
const MOVING = 'application/x-onespace-file'

const lifted = ref(false)
const over = ref(false)

function onDragStart(event) {
  if (!props.movable || remote.value) return
  lifted.value = true
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData(MOVING, props.file.name)
}

function onDragOver(event) {
  // Only a folder is a destination, and only for one of ours. A file dragged
  // from the desktop falls through to the page's own drop zone, which uploads
  // it.
  // A mount is read-only through the Drive, so it is not a drop target either.
  if (remote.value) return
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

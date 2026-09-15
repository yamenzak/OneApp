<template>
  <!--
    What you can do here, and what you can do to what you have chosen.

    A command bar rather than two buttons and a row of menus, which is what
    this was: New and a view toggle on the header's line, the verbs hidden
    behind a menu on each row, and a floating bar that appeared only once
    something was ticked. Three places to look for one question — "what can I
    do?" — and none of them answers it while nothing is selected.

    Every file manager on the reference board draws this row and they all draw
    it the same way, because it works: the verbs in the open, labelled while
    there is room, and **the row changes with the selection**. Nothing chosen
    is about the place you are in; something chosen is about the thing you
    chose. That is also why there is no disabled-Delete sitting there when
    nothing is selected — a row of greyed words is a row that teaches people
    to stop reading it.

    Labels collapse to icons before anything is dropped, and `More` takes what
    is left, so the same bar is honest at 560px and at 1200.
  -->
  <div
    data-slot="drive-commands"
    class="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-outline-gray-2 px-2 py-1.5"
  >
    <!--
      A mount: browsed, never written to. So the two verbs that mean anything
      on somebody else's host, and the slot for the connection's own menu.
    -->
    <template v-if="remote">
      <Button
        icon-left="lucide-refresh-cw"
        variant="ghost"
        :label="__('Check again')"
        :tooltip="__('Ask the host again')"
        :loading="rereading"
        @click="emit('reread')"
      />
      <slot name="mount" />
    </template>

    <!-- Nothing chosen: this is about the place. -->
    <template v-else-if="!picked.length">
      <Dropdown :options="makeOptions">
        <Button
          variant="solid"
          icon-left="lucide-plus"
          icon-right="lucide-chevron-down"
          :label="__('New')"
          :disabled="!can.can(CAN.CREATE)"
          :tooltip="can.why(CAN.CREATE) || __('Make something here')"
          :loading="making"
        />
      </Dropdown>
      <Button
        :icon-left="wide ? 'lucide-upload' : undefined"
        :icon="wide ? undefined : 'lucide-upload'"
        variant="ghost"
        :label="__('Upload')"
        :tooltip="__('Upload files')"
        :disabled="!can.can(CAN.CREATE)"
        @click="emit('upload')"
      />

      <span v-if="!landing" class="mx-1 h-5 w-px shrink-0 bg-surface-gray-4" />

      <Dropdown v-if="!landing" :options="orderOptions">
        <Button
          :icon-left="wide ? 'lucide-arrow-up-down' : undefined"
          :icon="wide ? undefined : 'lucide-arrow-up-down'"
          variant="ghost"
          :label="__('Sort')"
          :disabled="!can.can(CAN.SORT)"
          :tooltip="can.why(CAN.SORT) || __('Sorted by {0}', [orderName])"
        />
      </Dropdown>
    </template>

    <!--
      Something chosen: this is about it.

      Open and Rename are the two that only make sense for one thing, so they
      are drawn for one thing. Everything else takes a selection of any size,
      which is why the bar does not change shape again between one and forty.
    -->
    <template v-else-if="picked.length">
      <Button
        v-if="one && !trashed"
        :icon-left="wide ? 'lucide-external-link' : undefined"
        :icon="wide ? undefined : 'lucide-external-link'"
        variant="ghost"
        :label="__('Open')"
        :tooltip="__('Open')"
        @click="emit('open', one)"
      />
      <Button
        v-if="!trashed && !remote && !anyFolder"
        :icon-left="wide ? 'lucide-download' : undefined"
        :icon="wide ? undefined : 'lucide-download'"
        variant="ghost"
        :label="__('Download')"
        :tooltip="__('Download')"
        @click="emit('download')"
      />
      <Button
        v-if="one && !trashed && !remote && !one.is_folder"
        :icon-left="wide ? 'lucide-share-2' : undefined"
        :icon="wide ? undefined : 'lucide-share-2'"
        variant="ghost"
        :label="__('Share')"
        :tooltip="__('Share')"
        @click="emit('share', one)"
      />
      <Button
        v-if="one && !trashed && !remote"
        :icon-left="wide ? 'lucide-pencil-line' : undefined"
        :icon="wide ? undefined : 'lucide-pencil-line'"
        variant="ghost"
        :label="__('Rename')"
        :tooltip="__('Rename')"
        @click="emit('rename', one)"
      />
      <Button
        v-if="!trashed && !remote"
        :icon-left="wide ? 'lucide-folder-input' : undefined"
        :icon="wide ? undefined : 'lucide-folder-input'"
        variant="ghost"
        :label="__('Move')"
        :tooltip="__('Move')"
        @click="emit('move')"
      />

      <!-- The bin, and the two verbs that are only in it. -->
      <Button
        v-if="trashed"
        icon-left="lucide-rotate-ccw"
        variant="ghost"
        :label="__('Put it back')"
        :tooltip="__('Put it back')"
        @click="emit('restore')"
      />
      <Button
        v-if="!remote"
        :icon-left="wide ? (trashed ? 'lucide-trash-2' : 'lucide-trash-2') : undefined"
        :icon="wide ? undefined : 'lucide-trash-2'"
        variant="ghost"
        :theme="trashed ? 'red' : undefined"
        :label="trashed ? __('Delete for ever') : __('Move to the bin')"
        :tooltip="trashed ? __('Delete for ever') : __('Move to the bin')"
        @click="emit(trashed ? 'destroy' : 'trash')"
      />

      <Dropdown v-if="moreOptions.length" :options="moreOptions">
        <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" :tooltip="__('More')" />
      </Dropdown>

      <span class="mx-1 h-5 w-px shrink-0 bg-surface-gray-4" />

      <!-- The way out of having chosen. How *many* is not here: that is a fact
           about the list and it is said under the list, in the status bar,
           which is where every file manager has put it. -->
      <Button
        variant="ghost"
        size="sm"
        icon="lucide-x"
        :label="__('Clear the selection')"
        :tooltip="__('Clear')"
        @click="emit('clear')"
      />
    </template>

    <div class="flex-1" />

    <!--
      What kind of thing to show, on this line rather than on one of its own.

      It had a band to itself, under this one, which made four stacked bars
      between the window's title and the first file: path, commands, kinds,
      search. Windows Explorer has two and Google Drive has two, and they are
      right — every band is a strip of the window that is not the thing the
      window is for.

      Hidden while something is chosen, because the bar is then about what you
      chose and narrowing the list under a selection is a way to lose it.
    -->
    <slot v-if="!picked.length" name="kinds" />

    <!-- The two that are about how you are looking rather than at what: they
         stay put whatever is chosen, because moving them would make the row
         jump under the pointer.

         Not on Home, which is not a list: there is no grid of it to switch to
         and nothing selected to show the details of. A greyed pair there would
         be the row teaching people to stop reading it. -->
    <Button
      v-if="!landing"
      variant="ghost"
      :icon="grid ? 'lucide-list' : 'lucide-layout-grid'"
      :label="grid ? __('Show as a list') : __('Show as a grid')"
      :tooltip="grid ? __('Show as a list') : __('Show as a grid')"
      @click="emit('grid', !grid)"
    />
    <Button
      v-if="!landing"
      variant="ghost"
      icon="lucide-panel-right"
      :label="__('Details')"
      :tooltip="__('Details')"
      :class="details ? '!bg-surface-gray-3' : ''"
      @click="emit('details')"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Dropdown } from '@/ui'
import { CAN } from '@/shared/lib/capability'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The rows that are ticked. The bar is about the place when this is empty. */
  picked: { type: Array, default: () => [] },
  /** What this place offers and what it refuses — `capability.js`. */
  can: { type: Object, required: true },
  /** The New menu, built by the page: it knows about templates and mounts. */
  makeOptions: { type: Array, default: () => [] },
  /** And the order menu, plus the word for the order in force. */
  orderOptions: { type: Array, default: () => [] },
  orderName: { type: String, default: '' },
  /** Verbs that do not earn a place on the row — see `moreOptions`. */
  moreOptions: { type: Array, default: () => [] },
  grid: { type: Boolean, default: false },
  details: { type: Boolean, default: false },
  making: { type: Boolean, default: false },
  /** The bin, where the two verbs are different ones. */
  trashed: { type: Boolean, default: false },
  /** A mount, which the Drive reads and does not write to. */
  remote: { type: Boolean, default: false },
  /** Whether the host is being asked again, so Check again says so. */
  rereading: { type: Boolean, default: false },
  /** Whether there is room for words beside the glyphs. */
  wide: { type: Boolean, default: true },
  /**
   * Home, which is a landing rather than a folder — `DriveHome.vue`.
   *
   * New and Upload still mean what they mean there; Sort, the grid and the
   * details pane do not, because there is no one list to sort, lay out as
   * cards, or pick a row of.
   */
  landing: { type: Boolean, default: false },
})

const emit = defineEmits([
  'upload', 'open', 'download', 'share', 'rename', 'move',
  'trash', 'restore', 'destroy', 'clear', 'grid', 'details', 'reread',
])

/** The one chosen thing, for the verbs that only mean anything singly. */
const one = computed(() => (props.picked.length === 1 ? props.picked[0] : null))

/** Whether a folder is in the selection, which is what Download cannot take. */
const anyFolder = computed(() => props.picked.some((file) => file.is_folder))
</script>

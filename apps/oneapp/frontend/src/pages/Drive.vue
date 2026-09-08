<template>
  <!--
    Every file in the workspace, in one place. A rail of places, a path, and a
    list or a grid. What is new is underneath: these are Frappe `File` rows, the
    same ones an attachment is, so nothing here is a second store.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center gap-1">
      <!-- The rail, on a phone: the shell draws a sidebar only on a desktop.
           The same list, from the same module, so the two cannot drift. -->
      <Dropdown v-if="isMobile" :options="placeOptions">
        <Button
          data-slot="drive-places"
          icon-right="lucide-chevron-down"
          variant="ghost"
          :label="placeName"
        />
      </Dropdown>
      <Breadcrumbs :items="crumbs" />
    </nav>

    <div class="flex shrink-0 items-center gap-2">
      <FormControl
        v-model="drive.search.value"
        type="text"
        :placeholder="__('Search files')"
        class="w-28 sm:w-48"
        @input="onSearch"
      />
      <!-- List or grid, remembered: a person who wants thumbnails wants them
           on every folder, not once. -->
      <Button
        :icon="grid ? 'lucide-list' : 'lucide-layout-grid'"
        :label="grid ? __('Show as a list') : __('Show as a grid')"
        :tooltip="grid ? __('Show as a list') : __('Show as a grid')"
        variant="ghost"
        @click="setGrid(!grid)"
      />
      <!--
        Icon-only on a phone. `icon` rather than `icon-left` is what makes a
        Button icon-only; the label stays either way, because it is also the
        accessible name.
      -->
      <Button
        v-if="place === 'trash'"
        :icon="isMobile ? 'lucide-trash-2' : undefined"
        :icon-left="isMobile ? undefined : 'lucide-trash-2'"
        theme="red"
        :label="__('Empty the bin')"
        :tooltip="__('Empty the bin')"
        :disabled="!drive.files.value.length || drive.busy.value"
        @click="emptying = true"
      />
      <template v-else>
        <!--
          Upload. A plain input rather than `FileUploader`: the queue is
          `useUploads`, which outlives this page, and a component that owns
          reactive upload state would end where the page does.
        -->
        <!-- A hidden file input is the file picker itself; `FormControl` draws
             a labelled control and there is nothing here to label. -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <input
          ref="chooser"
          name="drive-upload"
          type="file"
          multiple
          class="hidden"
          @change="chosenFiles"
        >
        <Button
          :icon="isMobile ? 'lucide-upload' : undefined"
          :icon-left="isMobile ? undefined : 'lucide-upload'"
          :label="__('Upload')"
          :tooltip="__('Upload files')"
          @click="chooser?.click()"
        />
        <!--
          Everything made rather than uploaded, behind one button — a folder
          included. A dropdown rather than a row of buttons, because a
          workspace with an estimator template starts from it far more often
          than from a blank grid, and because "New folder" sitting beside "New"
          was two buttons for one idea: the first thing anybody asks of either
          is "make me something here".
        -->
        <Dropdown :options="makeOptions">
          <Button
            :icon="isMobile ? 'lucide-plus' : undefined"
            :icon-left="isMobile ? undefined : 'lucide-plus'"
            :icon-right="isMobile ? undefined : 'lucide-chevron-down'"
            variant="solid"
            :label="__('New')"
            :tooltip="__('New file')"
            :loading="making"
          />
        </Dropdown>
      </template>
    </div>
  </PageHeader>

  <!-- The rail is the shell's, drawn into its `#sidebar` slot the way Mail's
       is — a page that drew its own would be two rails on one screen. -->
  <div class="flex h-full min-h-0">
    <!--
      Drop anywhere in the pane, not only on the list: a person dragging four
      files at an empty folder aims at the empty state.

      `dragenter`/`dragleave` are counted rather than paired — both fire for
      every child the pointer crosses.
    -->
    <div
      class="flex min-w-0 flex-1 flex-col p-5"
      data-slot="drive-dropzone"
      :class="dragging ? 'rounded-6 ring-2 ring-inset ring-outline-gray-3' : ''"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <!-- What the bin is, said where somebody deciding whether to empty it is
           looking: thirty days is the promise the sweep keeps. -->
      <Alert
        v-if="place === 'trash' && drive.files.value.length"
        class="mb-4"
        theme="gray"
        :title="__('Everything here is deleted after thirty days')"
      >
        <template #description>
          {{ __('Until then it can be put back exactly where it was.') }}
        </template>
      </Alert>

      <div v-if="drive.loading.value && !drive.files.value.length" class="flex flex-col gap-2">
        <Skeleton v-for="n in 8" :key="n" class="h-11 w-full" />
      </div>

      <Alert v-else-if="drive.error.value" theme="red" :title="__('Your files did not load')">
        <template #description>{{ drive.error.value }}</template>
      </Alert>

      <EmptyState
        v-else-if="!drive.files.value.length"
        :icon="place === 'trash' ? 'lucide-trash-2' : 'lucide-folder-open'"
        :title="EMPTY[place].title"
        :description="EMPTY[place].description"
      />

      <div v-else class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        <!-- Select-all is a row of its own rather than a header cell, because
             the list has no header: a file manager's columns are fixed. -->
        <div
          v-if="!grid"
          class="flex items-center gap-2 pb-1 text-p-xs text-ink-gray-5"
        >
          <Checkbox
            :model-value="drive.allSelected.value"
            :aria-label="__('Select everything here')"
            class="ms-2.5"
            @update:model-value="drive.toggleAll"
          />
          <span>{{ counted }}</span>
        </div>

        <ContextMenu :options="rowMenu">
        <div
          :class="
            grid
              ? 'grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6'
              : 'flex flex-col'
          "
        >
          <FileRow
            v-for="file in drive.files.value"
            :key="file.name"
            :file="file"
            :link="routeFor(file)"
            :grid="grid"
            selectable
            actions
            movable
            :selected="drive.picked.value.has(file.name)"
            :trashed="place === 'trash'"
            @menu="(options) => (rowMenu = options)"
            @move-into="moveInto"
            @open="open"
            @select="drive.toggle"
            @favourite="drive.favourite"
            @share="startShare"
            @rename="startRename"
            @move="(one) => startMove([one])"
            @trash="(one) => drive.trash(one)"
            @restore="(one) => drive.restore(one)"
            @destroy="(one) => drive.destroy(one)"
          />
        </div>
        </ContextMenu>

        <Button
          v-if="drive.more.value"
          variant="ghost"
          :label="__('Load more')"
          :loading="drive.loading.value"
          @click="drive.load({ append: true })"
        />
      </div>
    </div>
  </div>

  <!-- What you can do with what you have chosen, over the list rather than in
       the header: a bar at the top means looking away from the thing you are
       acting on. -->
  <div
    v-if="drive.anySelected.value"
    data-slot="drive-selection"
    class="pointer-events-none fixed inset-x-0 bottom-24 z-10 flex justify-center px-4 sm:bottom-6"
  >
    <div
      class="pointer-events-auto flex max-w-full flex-wrap items-center justify-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-3 py-2 shadow-lg"
    >
      <!-- Not on a phone: the row above already says "2 of 50 chosen", and
           repeating it pushes the buttons onto a second line. -->
      <span v-if="!isMobile" class="px-1 text-p-sm text-ink-gray-7">{{ chosen }}</span>
      <template v-if="place === 'trash'">
        <Button
          icon-left="lucide-rotate-ccw"
          :label="__('Put back')"
          :tooltip="__('Put back')"
          :loading="drive.busy.value"
          @click="drive.restore(drive.selected.value)"
        />
        <Button
          icon-left="lucide-trash-2"
          theme="red"
          :label="isMobile ? __('Delete') : __('Delete for good')"
          :tooltip="__('Delete for good')"
          :loading="drive.busy.value"
          @click="drive.destroy(drive.selected.value)"
        />
      </template>
      <template v-else>
        <Button
          icon-left="lucide-folder-input"
          :label="__('Move')"
          :loading="drive.busy.value"
          @click="startMove(drive.selected.value)"
        />
        <Button
          icon-left="lucide-trash-2"
          theme="red"
          :label="isMobile ? __('Bin') : __('Move to the bin')"
          :tooltip="__('Move to the bin')"
          :loading="drive.busy.value"
          @click="drive.trash(drive.selected.value)"
        />
      </template>
      <Button
        icon="lucide-x"
        variant="ghost"
        :label="__('Clear the selection')"
        :tooltip="__('Clear the selection')"
        @click="drive.clear"
      />
    </div>
  </div>

  <UploadTray />

  <FilePreview v-model="previewing" :file="looking" />
  <FileShare v-model="sharing" :file="looking" />
  <ImportSheet v-model="importing" :folder="folder" />

  <FolderPicker v-model="moving" :moving="toMove" @chosen="intoFolder" />

  <Dialog v-model="naming" :title="__('New folder')">
    <template #default>
      <FormControl v-model="folderName" :label="__('Name')" @keyup.enter="makeFolder" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Make it')"
        :loading="drive.busy.value"
        @click="makeFolder"
      />
    </template>
  </Dialog>

  <Dialog v-model="renaming" :title="__('Rename')">
    <template #default>
      <FormControl v-model="newName" :label="__('Name')" @keyup.enter="finishRename" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Rename')"
        :loading="drive.busy.value"
        @click="finishRename"
      />
    </template>
  </Dialog>

  <!-- The one that does not come back gets a question in front of it. -->
  <Dialog v-model="emptying" :title="__('Empty the bin')">
    <template #default>
      <p class="text-p-base text-ink-gray-7">
        {{ __('Everything in the bin is deleted for good. This cannot be undone.') }}
      </p>
    </template>
    <template #actions>
      <Button
        variant="solid"
        theme="red"
        :label="__('Delete it all')"
        :loading="drive.busy.value"
        @click="finishEmpty"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Alert,
  Breadcrumbs,
  Button,
  Checkbox,
  ContextMenu,
  Dialog,
  Dropdown,
  FormControl,
  PageHeader,
  Skeleton,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FilePreview from '../components/drive/FilePreview.vue'
import FileRow from '../components/drive/FileRow.vue'
import FileShare from '../components/drive/FileShare.vue'
import FolderPicker from '../components/drive/FolderPicker.vue'
import UploadTray from '../components/drive/UploadTray.vue'
import ImportSheet from '../components/sheets/ImportSheet.vue'
import { useDrive } from '../composables/useDrive'
import { useNewFile } from '../composables/useNewFile'
import { useUploads } from '../composables/useUploads'
import { routeFor } from '../lib/files/files'
import { useIsMobile } from '@/lib/shell/breakpoint'
import { __ } from '@/lib/runtime/translate'
import { PLACES, labelOf } from '../components/drive/places'

const GRID_KEY = 'onespace:drive:grid'

// What an empty place means, which is different in each: an empty bin is good
// news and an empty folder is an invitation.
const EMPTY = {
  home: {
    title: __('Nothing here yet'),
    description: __('Upload a file, or make a folder to put files in.'),
  },
  recents: {
    title: __('Nothing opened yet'),
    description: __('Files you open show up here.'),
  },
  favourites: {
    title: __('No favourites'),
    description: __('Heart a file to keep it here.'),
  },
  shared: {
    title: __('Nothing shared with you'),
    description: __('Files other people share with you appear here.'),
  },
  trash: {
    title: __('The bin is empty'),
    description: __('Deleted files wait here for thirty days.'),
  },
  // Not in the rail. `?place=all` is the flat view of everything this person
  // can see — what the file picker asks for.
  all: { title: __('No files yet'), description: __('Upload a file to start.') },
}

const route = useRoute()
// The header is a breadcrumb, a search box and two buttons. On a phone that is
// more than 412px holds, so the buttons lose their words and keep their
// tooltips.
const isMobile = useIsMobile()

// The place and the folder are in the URL, so a folder is somewhere you can
// send a colleague. A place that is not one of these is a typo, and a typo must
// not be a blank page: `EMPTY[place]` is read unconditionally by the template.
const place = computed(() =>
  Object.hasOwn(EMPTY, route.query.place) ? route.query.place : 'home',
)
const folder = computed(() => route.query.folder || '')

const drive = useDrive({ place, folder })

// --------------------------------------------------------------------------
// Getting files in
// --------------------------------------------------------------------------

const uploads = useUploads()
const chooser = ref(null)

// A finished upload lands in a folder somebody may be looking at. Re-reading
// the place rather than pushing a row in: the server decided the name, the size
// and whether the quota allowed it at all.
uploads.onFinished((one) => {
  if (one.folder === (folder.value || 'Home')) drive.load()
})

function chosenFiles(event) {
  uploads.add([...(event.target.files || [])], folder.value || 'Home')
  // Reset, so choosing the same file twice fires twice.
  event.target.value = ''
}

// Counted, not paired: `dragenter` and `dragleave` both fire for every child
// the pointer crosses.
const dragDepth = ref(0)
const dragging = computed(() => dragDepth.value > 0)

function onDragEnter(event) {
  if (!event.dataTransfer?.types?.includes('Files')) return
  dragDepth.value += 1
}

function onDragLeave() {
  dragDepth.value = Math.max(0, dragDepth.value - 1)
}

function onDrop(event) {
  dragDepth.value = 0
  const files = [...(event.dataTransfer?.files || [])]
  // A row dragged onto empty space, not a file from the desktop. The row's own
  // drop handler covers the case that means something.
  if (!files.length) return
  if (place.value === 'trash') return
  uploads.add(files, folder.value || 'Home')
}

/** A row dropped on a folder row. */
function moveInto(target, names) {
  const moving = drive.files.value.filter((one) => names.includes(one.name))
  if (moving.length) drive.move(moving, target.name)
}

// One menu for the whole list, filled by whichever row was end-clicked —
// frappe-ui's own pattern, and why there is not a menu instance per row.
const rowMenu = ref([])

const placeName = computed(() => labelOf(place.value))
const placeOptions = computed(() =>
  PLACES.map((one) => ({
    label: one.label,
    icon: one.icon,
    route: { name: 'Drive', query: { place: one.value } },
  })),
)

const crumbs = computed(() => [
  // On a phone the dropdown beside this already names the place, and a trail
  // reading "Files / Files / Drawings" is one crumb too many in 412px.
  ...(isMobile.value
    ? []
    : [{ label: __('Files'), route: { name: 'Drive', query: { place: place.value } } }]),
  ...drive.path.value.map((one) => ({
    label: one.label,
    route: { name: 'Drive', query: { place: 'home', folder: one.name } },
  })),
])

const counted = computed(() => {
  const shown = drive.files.value.length
  const chosenNow = drive.picked.value.size
  if (chosenNow) return __('{0} of {1} chosen', [chosenNow, shown])
  // Whole sentences rather than a number glued to a word: the plural and the
  // "and there is more" are one phrase in some languages and two in others.
  if (drive.more.value) {
    return shown === 1
      ? __('1 thing, more below')
      : __('{0} things, more below', [shown])
  }
  return shown === 1 ? __('1 thing') : __('{0} things', [shown])
})

const chosen = computed(() => {
  const count = drive.picked.value.size
  return count === 1 ? __('1 thing chosen') : __('{0} things chosen', [count])
})

// Per-person and per-browser, like the theme: a view preference is not
// something the workspace has an opinion about.
const grid = ref(read(GRID_KEY) === '1')
function setGrid(wanted) {
  grid.value = wanted
  try {
    localStorage.setItem(GRID_KEY, wanted ? '1' : '0')
  } catch {
    // A browser with site data blocked still gets the toggle, just not the
    // memory of it.
  }
}
function read(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

// Which file the dialogs are about. One ref, because only one of them is open.
const looking = ref(null)
const previewing = ref(false)
const sharing = ref(false)
const naming = ref(false)
const renaming = ref(false)
const moving = ref(false)
const emptying = ref(false)
const folderName = ref('')
const newName = ref('')
const toMove = ref([])
const importing = ref(false)

// Anything with an address is a link and navigates itself — a folder, a sheet,
// a document, a text file. What is left is the files that are looked at rather
// than opened, and looking is what this does: the download is one button
// further in, which is the right way round.
function open(file) {
  looking.value = file
  previewing.value = true
}

// The only things in this product that are made rather than uploaded, shared
// with the record's Files tab. Importing a spreadsheet is the Drive's alone:
// it opens a dialog this page owns.
const { making, options: newOptions, loadTemplates } = useNewFile(
  () => ({ folder: folder.value || '' }),
  () => [{
    label: __('Import a spreadsheet'),
    icon: 'lucide-file-up',
    onClick: () => { importing.value = true },
  }],
)

/**
 * The New menu, with a folder at the top of it.
 *
 * A folder is the Drive's alone — a record's Files tab has folders nowhere to
 * put them — so it is added here rather than in `useNewFile`, which both
 * surfaces share. Ungrouped and first, which the Menu turns into a group of
 * its own with a rule under it: a folder is not something you write and not
 * something you calculate, and giving it a heading of its own for one row is
 * more furniture than the row is worth.
 */
const makeOptions = computed(() => [
  {
    label: __('New folder'),
    icon: 'lucide-folder-plus',
    onClick: () => { naming.value = true },
  },
  ...newOptions.value,
])

function startShare(file) {
  looking.value = file
  sharing.value = true
}

function startRename(file) {
  looking.value = file
  newName.value = file.file_name || ''
  renaming.value = true
}

function startMove(what) {
  toMove.value = what
  moving.value = true
}

async function intoFolder(into) {
  await drive.move(toMove.value, into)
  drive.clear()
}

async function makeFolder() {
  const title = folderName.value.trim()
  if (!title) return
  await drive.newFolder(title)
  if (!drive.error.value) {
    naming.value = false
    folderName.value = ''
  }
}

async function finishRename() {
  const title = newName.value.trim()
  if (!title || !looking.value) return
  await drive.rename(looking.value, title)
  if (!drive.error.value) renaming.value = false
}

async function finishEmpty() {
  await drive.emptyBin()
  emptying.value = false
}

let typing = null
function onSearch() {
  clearTimeout(typing)
  typing = setTimeout(() => drive.load(), 300)
}

onMounted(() => {
  drive.load()
  loadTemplates()
})
watch([place, folder], () => {
  drive.clear()
  drive.load()
})
</script>

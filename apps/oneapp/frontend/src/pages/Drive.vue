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
  <div class="flex h-full min-h-0 gap-2">
    <!--
      Drop anywhere in the pane, not only on the list: a person dragging four
      files at an empty folder aims at the empty state.

      `dragenter`/`dragleave` are counted rather than paired — both fire for
      every child the pointer crosses.
    -->
    <div
      class="flex min-w-0 flex-1 flex-col rounded-6 bg-surface-base p-5"
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
        <!--
          The header, which is a row of its own rather than a set of column
          cells: a file's name is a column and everything after it — who,
          when, how big — is one right-hand cluster, so headings over it would
          label nothing. Select-all on the left, the count beside it, and the
          order on the right.

          Drawn over the grid too. The grid has no rows to head, but "biggest
          first" is a question you ask of thumbnails as often as of a list, and
          a control that disappears when you switch view is a control you stop
          trusting.
        -->
        <div class="flex items-center gap-2 pb-1 text-p-xs text-ink-gray-5">
          <template v-if="!grid">
            <Checkbox
              :model-value="drive.allSelected.value"
              :aria-label="__('Select everything here')"
              class="ms-2.5"
              @update:model-value="drive.toggleAll"
            />
            <span>{{ counted }}</span>
          </template>
          <span v-else>{{ counted }}</span>

          <!-- Wrapped, because `Dropdown`'s root is reka's provider and a class
               on it has no element to land on. -->
          <div class="ms-auto">
          <Dropdown :options="orderOptions">
            <Button
              variant="ghost"
              size="sm"
              data-slot="drive-order"
              :icon-left="drive.descending.value
                ? 'lucide-arrow-down-narrow-wide'
                : 'lucide-arrow-up-narrow-wide'"
              icon-right="lucide-chevron-down"
              :label="orderName"
              :tooltip="__('How these are ordered')"
            />
          </Dropdown>
          </div>
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
            :inline="isMobile ? [] : INLINE"
            :dense="editing && previewing && !isMobile"
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

    <!--
      The file you are looking at, beside the list rather than over it.

      A dialog was the wrong shape for a file manager: looking at a photograph
      is how you decide which photograph, and a modal makes that a sequence of
      open-look-close-open rather than a walk down the list. The same pane a
      record opens in, for the same reason and with the same resizer — and on a
      phone `RecordPane` draws itself as a full overlay, which is what a
      dialog was doing there anyway.

      Only for what has no editor of its own. A sheet, a document and a folder
      are places with addresses, and clicking one goes there; a `.zip` is not,
      and this is where it opens.
    -->
    <!--
      More of the window than a record pane takes, when it holds an editor.
      A record is fields beside a list; a spreadsheet is the thing you came to
      work in, and 45% of a laptop is four columns.
    -->
    <RecordPane
      v-if="looking && previewing"
      :max-share="editing ? 0.72 : 0.45"
      :min="editing ? editorFloor() : undefined"
    >
      <template #body>
        <div class="flex h-full min-h-0 flex-col overflow-hidden rounded-6 bg-surface-base">
          <!--
            No header of ours over an editor. Both editors bring their own
            identity bar — the name, a way back, and their own File menu — and
            a second one above it is the file's name said twice with a rule
            between. What this header offers that theirs does not (a link, a
            download) a sheet offers under File and a document under its own
            menu.
          -->
          <header
            v-if="!editing"
            class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 p-3"
          >
            <h2 class="flex min-w-0 flex-1 items-center gap-1.5">
              <span class="truncate text-base text-ink-gray-8">{{ looking.file_name }}</span>
              <AiMark v-if="looking._ai" :mark="looking._ai" />
            </h2>
            <!--
              A link, not `FileShare`. Two different things wear the word
              share: `FileShare` is a `DocShare` row and needs the other person
              to have a login here, and this is the one for the consultant who
              does not. The row's menu offers the first; a file you are looking
              at is usually a file you are about to send somebody.
            -->
            <Button
              icon="lucide-link"
              variant="ghost"
              :label="__('Share a link')"
              :tooltip="__('Share a link')"
              @click="linking = true"
            />
            <Button
              icon="lucide-download"
              variant="ghost"
              :label="__('Download')"
              :tooltip="__('Download')"
              @click="downloadLooking"
            />
            <Button
              icon="lucide-x"
              variant="ghost"
              :label="__('Close')"
              :tooltip="__('Close')"
              data-slot="drive-pane-close"
              @click="previewing = false"
            />
          </header>

          <!--
            A sheet and a document open here rather than on a page of their
            own, and they open editable: the point of a file manager is to work
            in a file without losing the folder you found it in. Cmd-click
            still opens either on its own page, because the row is still a
            link — see `FileRow`.

            `:key` on the name, because both editors load their document once
            on mount: without it, clicking a second sheet would keep the first
            one on screen.
          -->
          <SheetEditor
            v-if="looking.custom_kind === 'Sheet'"
            :key="looking.name"
            :id="looking.name"
            :host-menu="[]"
            @close="previewing = false"
          />

          <Doc
            v-else-if="looking.custom_kind === 'Doc'"
            :key="looking.name"
            :name="looking.name"
          />

          <div v-else class="min-h-0 flex-1 overflow-auto p-3">
            <FileSurface :file="looking" :live="previewing" :tall="false" />
          </div>
        </div>
      </template>
    </RecordPane>
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

  <FileShare v-model="sharing" :file="looking" />

  <ShareLink v-model="linking" :file="looking" />
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
import AiMark from '../components/AiMark.vue'
import EmptyState from '../components/EmptyState.vue'
import FileSurface from '../components/drive/FileSurface.vue'
import FileRow from '../components/drive/FileRow.vue'
import FileShare from '../components/drive/FileShare.vue'
import ShareLink from '../components/drive/ShareLink.vue'
import FolderPicker from '../components/drive/FolderPicker.vue'
import UploadTray from '../components/drive/UploadTray.vue'
import RecordPane from '../components/screen/record/RecordPane.vue'
import SheetEditor from '../components/sheets/editor/index.vue'
import Doc from './Doc.vue'
import ImportSheet from '../components/sheets/ImportSheet.vue'
import { useDrive } from '../composables/useDrive'
import { useNewFile } from '../composables/useNewFile'
import { useUploads } from '../composables/useUploads'
import { downloadUrl, routeFor } from '../lib/files/files'
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

/*
 * What a place can be put in order by, and what each is called.
 *
 * Four, and not every column the server would allow: a sort control is a list
 * you read every time you open it, and the fifth entry is the one that makes
 * you read rather than recognise. Kind is in it because "show me the sheets"
 * is a real question in a folder of forty attachments, and grouping by it is
 * the nearest thing to an answer this list has.
 *
 * The empty key is the place's own — Home leads with folders and then names,
 * Recents with what was opened last — and it is first, because "however this
 * place normally is" is where most people want to be.
 */
const ORDERS = [
  { key: '', label: __('However this place is'), icon: 'lucide-sparkles' },
  { key: 'name', label: __('Name'), icon: 'lucide-case-sensitive' },
  { key: 'modified', label: __('Last changed'), icon: 'lucide-clock' },
  { key: 'size', label: __('Size'), icon: 'lucide-hard-drive' },
  { key: 'kind', label: __('Kind'), icon: 'lucide-shapes' },
]

const orderName = computed(
  () => ORDERS.find((one) => one.key === drive.sort.value)?.label || ORDERS[0].label,
)

const orderOptions = computed(() => ORDERS.map((one) => ({
  label: one.label,
  icon: one.icon,
  // Ticked rather than only bolded: a menu of five where one is in force is a
  // menu that has to say which, and the arrow on the button says only which
  // way round it is.
  selected: one.key === drive.sort.value,
  onClick: () => drive.orderBy(one.key),
})))

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

/*
 * The kinds the pane opens rather than the router.
 *
 * A sheet and a document, because both have an editor that fits a column and
 * because opening one is the commonest thing anybody does in a file manager —
 * walking away from the list to do it is what makes a file manager feel like a
 * detour. Everything else either has no editor of ours or is a place with an
 * address, and both of those still navigate.
 */
// The kinds that open in the pane instead of on their own page — and only on
// a desktop. On a phone the pane is a full-screen overlay, so opening a sheet
// in it buys nothing the page does not already give and costs the URL and the
// back button. So there the row stays what it looks like: a link.
const INLINE = ['Sheet', 'Doc']

// Wider when the pane holds an editor. Four hundred and eighty pixels is a
// preview; it is not a spreadsheet, and a person who has to drag the resizer
// before they can read a row has been handed a chore rather than a feature.
//
// As the pane's *minimum* rather than by setting its width: the Resizer takes
// the remembered width on mount, so anything written before that is overwritten
// a frame later. A floor is declarative, survives the mount, and still lets
// somebody drag wider.
//
// A share of the window and not 860 flat. 860 on a 1280 laptop leaves the list
// 180 pixels — every name truncated to nothing, which is a file manager you
// cannot pick the next file from. Half the window, up to 860: six columns on a
// laptop and a proper grid on a large screen, and the list stays a list.
//: What the list keeps whatever is open beside it. Below this a row is dates
//: and a truncation, and picking the next file — the only reason the list is
//: still on screen — stops working.
const LIST_FLOOR = 420

const editorFloor = () => {
  const half = Math.max(560, window.innerWidth * 0.5)
  // The sidebar is outside this pane's window share, so the room to leave the
  // list is measured off what the content column actually has.
  const spare = window.innerWidth - LIST_FLOOR - 260
  return Math.round(Math.max(480, Math.min(860, half, spare)))
}

const editing = computed(() => INLINE.includes(looking.value?.custom_kind))

const downloadLooking = () => window.open(downloadUrl(looking.value.name), '_blank')
const sharing = ref(false)
const linking = ref(false)
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

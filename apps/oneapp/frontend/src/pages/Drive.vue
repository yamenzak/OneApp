<template>
  <!--
    Every file in the workspace, in one place.

    The layout is the one every file manager has had for thirty years and the
    reason to keep it is that nobody has to learn it: a rail of places, a path,
    and a list or a grid. What is new is underneath — these are Frappe `File`
    rows, the same ones an attachment is, so nothing here is a second store.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs" />
    </nav>

    <div class="flex shrink-0 items-center gap-2">
      <FormControl
        v-model="drive.search.value"
        type="text"
        placeholder="Search files"
        class="w-48"
        @input="onSearch"
      />
      <!-- List or grid, remembered. The same preference the record surface
           keeps about panes: a person who wants thumbnails wants them on every
           folder, not once. -->
      <Button
        :icon="grid ? 'lucide-list' : 'lucide-layout-grid'"
        :label="grid ? 'Show as a list' : 'Show as a grid'"
        :tooltip="grid ? 'Show as a list' : 'Show as a grid'"
        variant="ghost"
        @click="setGrid(!grid)"
      />
      <Button
        v-if="place === 'trash'"
        icon-left="lucide-trash-2"
        theme="red"
        label="Empty the bin"
        :disabled="!drive.files.value.length || drive.busy.value"
        @click="emptying = true"
      />
      <Button
        v-else
        icon-left="lucide-folder-plus"
        label="New folder"
        @click="naming = true"
      />
    </div>
  </PageHeader>

  <!--
    The rail is the shell's, drawn into its `#sidebar` slot the way Mail's is —
    a page that drew its own would be two rails on one screen, which is what
    the first version of this was.
  -->
  <div class="flex h-full min-h-0">
    <div class="flex min-w-0 flex-1 flex-col p-5">
      <!--
        What the bin is, said where somebody deciding whether to empty it is
        looking. Thirty days is the promise the sweep keeps, and a bin whose
        terms are only in the code is a bin nobody trusts.
      -->
      <Alert
        v-if="place === 'trash' && drive.files.value.length"
        class="mb-4"
        theme="gray"
        title="Everything here is deleted after thirty days"
      >
        <template #description>
          Until then it can be put back exactly where it was.
        </template>
      </Alert>

      <div v-if="drive.loading.value && !drive.files.value.length" class="flex flex-col gap-2">
        <Skeleton v-for="n in 8" :key="n" class="h-11 w-full" />
      </div>

      <Alert v-else-if="drive.error.value" theme="red" title="These files could not be loaded">
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
             the list has no header: a file manager's columns are fixed and a
             header band over four of them is chrome for nothing. -->
        <div
          v-if="!grid"
          class="flex items-center gap-2 pb-1 text-p-xs text-ink-gray-5"
        >
          <Checkbox
            :model-value="drive.allSelected.value"
            aria-label="Select everything here"
            class="ml-2.5"
            @update:model-value="drive.toggleAll"
          />
          <span>{{ counted }}</span>
        </div>

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
            :grid="grid"
            selectable
            actions
            :selected="drive.picked.value.has(file.name)"
            :trashed="place === 'trash'"
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

        <Button
          v-if="drive.more.value"
          variant="ghost"
          label="Load more"
          :loading="drive.loading.value"
          @click="drive.load({ append: true })"
        />
      </div>
    </div>
  </div>

  <!--
    What you can do with what you have chosen, over the list rather than in the
    header: the selection is down here, and a bar at the top means looking away
    from the thing you are acting on.
  -->
  <div
    v-if="drive.anySelected.value"
    data-slot="drive-selection"
    class="pointer-events-none fixed inset-x-0 bottom-6 z-10 flex justify-center px-4"
  >
    <div
      class="pointer-events-auto flex items-center gap-2 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-3 py-2 shadow-lg"
    >
      <span class="px-1 text-p-sm text-ink-gray-7">{{ chosen }}</span>
      <template v-if="place === 'trash'">
        <Button
          icon-left="lucide-rotate-ccw"
          label="Put back"
          :loading="drive.busy.value"
          @click="drive.restore(drive.selected.value)"
        />
        <Button
          icon-left="lucide-trash-2"
          theme="red"
          label="Delete for good"
          :loading="drive.busy.value"
          @click="drive.destroy(drive.selected.value)"
        />
      </template>
      <template v-else>
        <Button
          icon-left="lucide-folder-input"
          label="Move"
          :loading="drive.busy.value"
          @click="startMove(drive.selected.value)"
        />
        <Button
          icon-left="lucide-trash-2"
          theme="red"
          label="Move to the bin"
          :loading="drive.busy.value"
          @click="drive.trash(drive.selected.value)"
        />
      </template>
      <Button
        icon="lucide-x"
        variant="ghost"
        label="Clear the selection"
        tooltip="Clear the selection"
        @click="drive.clear"
      />
    </div>
  </div>

  <FilePreview v-model="previewing" :file="looking" />
  <FileShare v-model="sharing" :file="looking" />
  <FolderPicker v-model="moving" :moving="toMove" @chosen="intoFolder" />

  <Dialog v-model="naming" title="New folder">
    <template #default>
      <FormControl v-model="folderName" label="Name" @keyup.enter="makeFolder" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        label="Make it"
        :loading="drive.busy.value"
        @click="makeFolder"
      />
    </template>
  </Dialog>

  <Dialog v-model="renaming" title="Rename">
    <template #default>
      <FormControl v-model="newName" label="Name" @keyup.enter="finishRename" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        label="Rename"
        :loading="drive.busy.value"
        @click="finishRename"
      />
    </template>
  </Dialog>

  <!--
    The one that does not come back gets a question in front of it. Everything
    else in this page is undoable, which is exactly why this one is not obvious
    from context.
  -->
  <Dialog v-model="emptying" title="Empty the bin">
    <template #default>
      <p class="text-p-base text-ink-gray-7">
        Everything in the bin is deleted for good, along with the files
        themselves. This cannot be undone.
      </p>
    </template>
    <template #actions>
      <Button
        variant="solid"
        theme="red"
        label="Delete it all"
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
  Dialog,
  FormControl,
  PageHeader,
  Skeleton,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FilePreview from '../components/drive/FilePreview.vue'
import FileRow from '../components/drive/FileRow.vue'
import FileShare from '../components/drive/FileShare.vue'
import FolderPicker from '../components/drive/FolderPicker.vue'
import { useDrive } from '../composables/useDrive'

const GRID_KEY = 'onespace:drive:grid'

// What an empty place means, which is different in each of them: an empty bin
// is good news and an empty folder is an invitation.
const EMPTY = {
  home: { title: 'Nothing here yet', description: 'Upload a file or make a folder to start.' },
  recents: { title: 'Nothing opened yet', description: 'Files you open show up here.' },
  favourites: { title: 'No favourites', description: 'Heart a file to keep it here.' },
  shared: { title: 'Nothing shared with you', description: 'Files other people share appear here.' },
  trash: { title: 'The bin is empty', description: 'Deleted files wait here for thirty days.' },
  // Not in the rail. `?place=all` is the flat view of everything this person
  // can see — what the file picker asks for, and a URL worth being able to
  // type when you know the file exists and not where it is.
  all: { title: 'No files yet', description: 'Upload a file to start.' },
}

const route = useRoute()

// The place and the folder are in the URL, so a folder is somewhere you can
// send a colleague and the back button walks back up the tree.
//
// A place that is not one of these is a typo, and a typo must not be a blank
// page: `EMPTY[place]` is read unconditionally by the template.
const place = computed(() =>
  Object.hasOwn(EMPTY, route.query.place) ? route.query.place : 'home',
)
const folder = computed(() => route.query.folder || '')

const drive = useDrive({ place, folder })

const crumbs = computed(() => [
  { label: 'Files', route: { name: 'Drive', query: { place: place.value } } },
  ...drive.path.value.map((one) => ({
    label: one.label,
    route: { name: 'Drive', query: { place: 'home', folder: one.name } },
  })),
])

const counted = computed(() => {
  const shown = drive.files.value.length
  const chosenNow = drive.picked.value.size
  if (chosenNow) return `${chosenNow} of ${shown} chosen`
  return `${shown} ${shown === 1 ? 'thing' : 'things'}${drive.more.value ? ', more below' : ''}`
})

const chosen = computed(() => {
  const count = drive.picked.value.size
  return `${count} ${count === 1 ? 'thing' : 'things'} chosen`
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

// A folder is a link and navigates itself; this is only ever a file.
//
// Opening one looks at it rather than downloading it — the download is still
// there, one button further in, which is the right way round: the common case
// is wanting to see the thing.
function open(file) {
  looking.value = file
  previewing.value = true
}

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

onMounted(() => drive.load())
watch([place, folder], () => {
  drive.clear()
  drive.load()
})
</script>

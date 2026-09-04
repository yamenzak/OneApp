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
        v-model="search"
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
        v-if="place !== 'trash'"
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
      <div v-if="loading && !files.length" class="flex flex-col gap-2">
        <Skeleton v-for="n in 8" :key="n" class="h-11 w-full" />
      </div>

      <Alert v-else-if="error" theme="red" title="These files could not be loaded">
        <template #description>{{ error }}</template>
      </Alert>

      <EmptyState
        v-else-if="!files.length"
        :icon="place === 'trash' ? 'lucide-trash-2' : 'lucide-folder-open'"
        :title="EMPTY[place].title"
        :description="EMPTY[place].description"
      />

      <div v-else class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        <div
          :class="
            grid
              ? 'grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6'
              : 'flex flex-col'
          "
        >
          <FileRow
            v-for="file in files"
            :key="file.name"
            :file="file"
            :grid="grid"
            @open="open"
          />
        </div>

        <Button
          v-if="more"
          variant="ghost"
          label="Load more"
          :loading="loading"
          @click="load({ append: true })"
        />
      </div>
    </div>
  </div>

  <FilePreview v-model="previewing" :file="looking" />

  <Dialog v-model="naming" title="New folder">
    <template #default>
      <FormControl v-model="folderName" label="Name" @keyup.enter="makeFolder" />
      <ErrorMessage class="mt-2" :message="folderError" />
    </template>
    <template #actions>
      <Button variant="solid" label="Make it" :loading="making" @click="makeFolder" />
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
  Dialog,
  ErrorMessage,
  FormControl,
  PageHeader,
  Skeleton,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FilePreview from '../components/drive/FilePreview.vue'
import FileRow from '../components/drive/FileRow.vue'
import { workspace } from '../lib/workspace'

const PAGE = 50
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

const files = ref([])
const more = ref(false)
const loading = ref(false)
const error = ref('')
const search = ref('')
const naming = ref(false)
const folderName = ref('')
const folderError = ref('')
const making = ref(false)
const previewing = ref(false)
const looking = ref(null)

// The place and the folder are in the URL, so a folder is somewhere you can
// send a colleague and the back button walks back up the tree.
// A place that is not one of these is a typo, and a typo must not be a blank
// page: `EMPTY[place]` is read unconditionally by the template.
const place = computed(() =>
  Object.hasOwn(EMPTY, route.query.place) ? route.query.place : 'home',
)
const folder = computed(() => route.query.folder || '')

const path = ref([])
const crumbs = computed(() => [
  { label: 'Files', route: { name: 'Drive', query: { place: place.value } } },
  ...path.value.map((one) => ({
    label: one.label,
    route: { name: 'Drive', query: { place: 'home', folder: one.name } },
  })),
])

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

async function load({ append = false } = {}) {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.driveList({
      place: place.value,
      folder: folder.value,
      search: search.value,
      start: append ? files.value.length : 0,
      limit: PAGE,
    })
    files.value = append ? [...files.value, ...(found?.files || [])] : found?.files || []
    more.value = !!found?.more
    path.value = found?.path || []
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

// A folder is a link and navigates itself; this is only ever a file.
//
// Opening one looks at it rather than downloading it — the download is still
// there, one button further in, which is the right way round: the common case
// is wanting to see the thing.
function open(file) {
  looking.value = file
  previewing.value = true
}

let typing = null
function onSearch() {
  clearTimeout(typing)
  typing = setTimeout(() => load(), 300)
}

async function makeFolder() {
  making.value = true
  folderError.value = ''
  try {
    await workspace.driveNewFolder(folderName.value, folder.value)
    naming.value = false
    folderName.value = ''
    await load()
  } catch (e) {
    folderError.value = e.message || String(e)
  } finally {
    making.value = false
  }
}

watch(() => [place.value, folder.value], () => {
  search.value = ''
  load()
})

onMounted(() => load())
</script>

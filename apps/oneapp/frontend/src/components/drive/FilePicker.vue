<!--
  Attach a file: from the library, from this device, or from the camera.

  The component this whole arc was for. Before it there were five separate
  upload surfaces — the record's Meta tab, the attachment gallery, every Attach
  field, the mail composer — and none of them could pick something the
  workspace already had, so the same drawing was uploaded four times under four
  names.

  **Upload writes into the Drive and then picks the result**, which is the
  sentence that makes this one path rather than two. There is no second store
  and no "attached but not in the Drive": a file is a `File` row, and where it
  came from is not a property of it.

  Three sources, which is Frappe's own dialog minus the two we do not want.
  Its desk offers Library, Link, Camera and Google Drive
  (`frappe/public/js/frappe/file_uploader/FileUploader.vue`). Link is a `File`
  row that points at somebody else's server, which is an attachment that breaks
  when they tidy up and is indistinguishable from one that does not until
  somebody needs it. Google Drive is a second cloud beside the one we run, and
  the answer to "my files are somewhere else" is to bring them here once rather
  than to federate.

  The upload goes through `lib/attach.js`, so a two-gigabyte video attaches to
  a record by exactly the route it takes into the Drive — presigned, straight
  to R2. Before that this dialog posted through Frappe and a large attachment
  simply failed.
-->
<template>
  <Dialog v-model="open" :title="title" size="3xl">
    <template #default>
      <Tabs v-model="tab" :tabs="TABS">
        <template #tab-panel="{ tab: current }">
          <!-- ----------------------------------------------------------- -->
          <!-- The library                                                  -->
          <!-- ----------------------------------------------------------- -->
          <div
            v-if="current.value === 'library'"
            data-slot="picker-library"
            class="flex h-96 flex-col gap-3 py-4"
          >
            <FormControl
              v-model="search"
              type="text"
              placeholder="Search files"
              @input="onSearch"
            />

            <div v-if="loading" class="flex flex-col gap-2">
              <Skeleton v-for="n in 6" :key="n" class="h-11 w-full" />
            </div>

            <EmptyState
              v-else-if="!files.length"
              icon="lucide-folder-open"
              title="Nothing to choose from"
              :description="
                kind
                  ? `No ${kind.toLowerCase()} files here yet — upload one instead.`
                  : 'No files here yet — upload one instead.'
              "
            />

            <div v-else class="flex min-h-0 flex-1 flex-col overflow-y-auto">
              <FileRow
                v-for="file in files"
                :key="file.name"
                :file="file"
                @open="choose"
              />
            </div>
          </div>

          <!-- ----------------------------------------------------------- -->
          <!-- This device                                                  -->
          <!-- ----------------------------------------------------------- -->
          <div
            v-else-if="current.value === 'upload'"
            data-slot="picker-upload"
            class="flex h-96 items-center py-4"
          >
            <div
              data-slot="picker-dropzone"
              class="flex w-full flex-col items-center gap-3 rounded-6 border border-dashed py-12"
              :class="dragging ? 'border-outline-gray-4 bg-surface-gray-1' : 'border-outline-gray-2'"
              @dragenter.prevent="onDragEnter"
              @dragover.prevent
              @dragleave.prevent="onDragLeave"
              @drop.prevent="onDrop"
            >
              <LoadingIndicator v-if="sending" class="size-8 text-ink-gray-4" />
              <Icon v-else name="lucide-upload-cloud" class="size-8 text-ink-gray-4" />

              <!-- Frappe-ui's FileUploader is deliberately not used here: it
                   posts the whole body to Frappe, which is the thing a large
                   file cannot survive. -->
              <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
              <input
                ref="chooser"
                name="picker-upload"
                type="file"
                :accept="accept"
                :multiple="multiple"
                class="hidden"
                @change="chosen"
              >
              <Button
                variant="solid"
                :label="sending ? `Uploading ${progress}%` : 'Choose a file'"
                :loading="sending"
                @click="chooser?.click()"
              />
              <p class="text-p-xs text-ink-gray-5">
                Drop {{ multiple ? 'files' : 'a file' }} here, or choose from
                this device. It goes into the workspace's files, and gets used
                here.
              </p>
            </div>
          </div>

          <!-- ----------------------------------------------------------- -->
          <!-- The camera                                                   -->
          <!-- ----------------------------------------------------------- -->
          <CameraCapture
            v-else
            data-slot="picker-camera"
            :active="current.value === 'camera'"
            @taken="send"
          />
        </template>
      </Tabs>

      <ErrorMessage class="mt-2" :message="error" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  Icon,
  LoadingIndicator,
  Skeleton,
  Tabs,
} from '@/ui'
import CameraCapture from './CameraCapture.vue'
import EmptyState from '../EmptyState.vue'
import FileRow from './FileRow.vue'
import { putFile } from '../../lib/attach'
import { errorText } from '../../lib/errors'
import { workspace } from '../../lib/workspace'

// The library first, which is the whole argument for this dialog existing: the
// file somebody wants is usually one the workspace already has, and a dialog
// that opens on an upload button teaches everyone to upload it again.
const TABS = [
  { label: 'Library', value: 'library' },
  { label: 'This device', value: 'upload' },
  { label: 'Camera', value: 'camera' },
]

const props = defineProps({
  // Narrows all three: an Attach Image field offers only images to choose
  // from and only images to upload, rather than letting somebody pick a
  // spreadsheet for a cover photo.
  kind: { type: String, default: '' },
  // What the dialog is called. A caller doing something specific with the file
  // — importing a spreadsheet, say — is not "attaching" it, and a dialog that
  // says so is a dialog somebody has to read twice.
  title: { type: String, default: 'Attach a file' },
  // Extensions this caller can actually take, lowercase and without the dot.
  // Narrower than `kind`, and sometimes the only useful filter: a spreadsheet
  // and a Word document are both `Document` in the Drive's taxonomy, and only
  // one of them can be imported as a sheet.
  extensions: { type: Array, default: () => [] },
  // What the file is attached to, when it is attached to something. A file
  // picked here keeps its own life in the Drive either way.
  attachedTo: { type: Object, default: null },
  // Whether more than one may be taken at once. Off by default because most
  // callers write into a single field, where the second file would silently
  // replace the first.
  multiple: { type: Boolean, default: false },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['picked'])

const tab = ref(0)
const files = ref([])
const search = ref('')
const loading = ref(false)
const error = ref('')

const chooser = ref(null)
const dragging = ref(0)
const sending = ref(false)
const progress = ref(0)

const accept = computed(() => {
  if (props.extensions.length) return props.extensions.map((one) => `.${one}`).join(',')
  return props.kind === 'Image' ? 'image/*' : undefined
})

/** Whether this row is one the caller said it could take. */
function allowed(file) {
  if (!props.extensions.length) return true
  const name = file?.file_name || ''
  return props.extensions.some((one) => name.toLowerCase().endsWith(`.${one}`))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.driveList({
      // Every file this person can see, not the root folder. Almost every
      // file in a workspace is an attachment and lives in `Home/Attachments`,
      // so a picker that showed the root would show an empty drive.
      place: 'all',
      kind: props.kind,
      search: search.value,
      limit: 50,
    })
    // Folders are not a thing you can attach, so they are not offered — the
    // picker is flat on purpose, and search is how you reach into a folder.
    files.value = (found?.files || []).filter((one) => !one.is_folder && allowed(one))
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}

let typing = null
function onSearch() {
  clearTimeout(typing)
  typing = setTimeout(load, 300)
}

async function choose(file) {
  // Picking, when the picker is on a record, has to end where uploading ends:
  // attached. The server writes a second row pointing at the same object
  // rather than moving the file, because the file being picked is usually
  // already attached to something else — which is why it was worth picking.
  if (props.attachedTo?.doctype) {
    try {
      const made = await workspace.driveAttach(file.name, props.attachedTo)
      emit('picked', { ...file, name: made.name, file_url: made.file_url })
      open.value = false
      return
    } catch (e) {
      error.value = errorText(e)
      return
    }
  }

  emit('picked', file)
  open.value = false
}

// --------------------------------------------------------------------------
// Uploading
// --------------------------------------------------------------------------

/**
 * Send what was chosen, dropped or photographed.
 *
 * Serial, and the reason is the same one the Drive's queue gives: two at a
 * time is not twice as fast on one connection and is twice as likely to trip
 * the quota check halfway, leaving one file uploaded and one refused with no
 * way to tell which was which.
 */
async function send(...chosenFiles) {
  if (sending.value) return
  error.value = ''
  const list = usable(chosenFiles.flat().filter(Boolean))
  if (!list.length) return

  sending.value = true
  progress.value = 0
  try {
    for (const file of list) {
      const made = await putFile(file, {
        attachTo: props.attachedTo,
        onProgress: ({ percent }) => { progress.value = percent },
      })
      emit('picked', made)
    }
    open.value = false
  } catch (e) {
    error.value = errorText(e)
  } finally {
    sending.value = false
  }
}

function chosen(event) {
  const list = Array.from(event.target?.files || [])
  // So choosing the same file twice in a row still fires `change`.
  if (chooser.value) chooser.value.value = ''
  send(list)
}

/**
 * Refuse what the caller cannot take, before anything is uploaded.
 *
 * `accept` on the input is a hint the file dialog may ignore and a drop
 * ignores entirely, so it is checked here as well — and here is before the
 * upload rather than after, which is the difference between a message and a
 * file in the Drive that nothing wanted.
 */
function usable(list) {
  const good = list.filter((one) => allowed({ file_name: one.name }))
  if (good.length < list.length) {
    error.value = `Only ${props.extensions.map((one) => `.${one}`).join(', ')} files can go here.`
  }
  return good
}

// Counted rather than toggled: dragging over a child fires `dragleave` on the
// parent, so a boolean flickers the whole time the pointer is inside.
function onDragEnter() {
  dragging.value += 1
}

function onDragLeave() {
  dragging.value = Math.max(0, dragging.value - 1)
}

function onDrop(event) {
  dragging.value = 0
  const list = Array.from(event.dataTransfer?.files || [])
  // A directory arrives as a zero-byte `File` with no type, and uploading that
  // produces an empty file named after the folder.
  send(list.filter((one) => one.size || one.type))
}

// Loaded when the dialog opens rather than on mount: a picker that fetched a
// page of files behind every Attach field on a form would be one request per
// field on every record anybody opened.
watch(open, (showing) => {
  if (showing) {
    search.value = ''
    error.value = ''
    load()
  }
})
</script>

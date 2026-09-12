<!--
  Attach a file: from the library, from this device, or from the camera.

  **Upload writes into the Drive and then picks the result**, which is the
  sentence that makes this one path rather than two. There is no second store
  and no "attached but not in the Drive": a file is a `File` row, and where it
  came from is not a property of it.

  Three sources, which is Frappe's own dialog minus Link — a `File` row pointing
  at somebody else's server is an attachment that breaks when they tidy up — and
  Google Drive, which is a second cloud beside the one we run.

  The upload goes through `lib/files/attach.js`, so a two-gigabyte video
  attaches to a record by exactly the route it takes into the Drive.
-->
<template>
  <Dialog v-model="open" :title="title" size="3xl">
    <template #default>
      <Tabs v-model="tab" :tabs="TABS">
        <template #tab-panel="{ tab: current }">
          <!-- The library -->
          <div
            v-if="current.value === 'library'"
            data-slot="picker-library"
            class="flex h-96 flex-col gap-3 py-4"
          >
            <!-- The frame is `DataList` over `fileSource` — §B1. The same
                 query the Drive reads, over every file this person can see
                 rather than one folder. -->
            <DataList
              ref="library"
              :source="source"
              :skeleton="6"
              :page-length="PAGE"
              body-class="min-h-0 flex-1 overflow-y-auto"
              :search-placeholder="__('Search files')"
            >
              <template #row="{ row: file }">
                <FileRow :file="file" @open="choose" />
              </template>
            </DataList>
          </div>

          <!-- This device -->
          <div
            v-else-if="current.value === 'upload'"
            data-slot="picker-upload"
            class="flex h-96 items-center py-4"
          >
            <div
              data-slot="picker-dropzone"
              class="flex w-full flex-col items-center gap-3 rounded-6 border border-dashed border-outline-gray-2 py-12"
              v-drop-files="send"
            >
              <Icon name="lucide-upload-cloud" class="size-8 text-ink-gray-4" />

              <!-- frappe-ui's FileUploader is deliberately not used here: it
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
                :label="__('Choose a file')"
                @click="chooser?.click()"
              />
              <p class="text-p-xs text-ink-muted">
                {{
                  multiple
                    ? __('Drop files here, or choose them from this device. They go into your files and get used here.')
                    : __('Drop a file here, or choose one from this device. It goes into your files and gets used here.')
                }}
              </p>
              <!-- The ceiling, before it is hit rather than after — §D3. Empty
                   on a site that sends straight to storage, where the only
                   thing that refuses a large file is the quota. -->
              <p v-if="ceiling" class="text-p-xs text-ink-muted">{{ ceiling }}</p>
            </div>
          </div>

          <!-- The camera -->
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
import { Button, Dialog, ErrorMessage, Icon, Tabs } from '@/ui'
import CameraCapture from '@/modules/onestorage/components/CameraCapture.vue'
import DataList from '@/shared/components/DataList.vue'
import { PAGE, fileSource } from '@/shared/lib/list/files'
import FileRow from '@/modules/onestorage/components/FileRow.vue'
import { labelForKind } from '@/modules/onestorage/lib/files'
import { ceilingNote, withinCeiling } from '@/shared/lib/files/limits'
import { useUploads } from '@/shared/composables/useUploads'
import { errorText } from '@/shared/lib/runtime/errors'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

// The library first, which is the whole argument for this dialog existing: the
// file somebody wants is usually one the workspace already has.
const TABS = [
  { label: __('Library'), value: 'library' },
  { label: __('This device'), value: 'upload' },
  { label: __('Camera'), value: 'camera' },
]

const props = defineProps({
  // Narrows all three: an Attach Image field offers only images to choose from
  // and only images to upload.
  kind: { type: String, default: '' },
  // What the dialog is called. A caller importing a spreadsheet is not
  // "attaching" it.
  title: { type: String, default: () => __('Attach a file') },
  // Extensions this caller can actually take, lowercase and without the dot.
  // Narrower than `kind`, and sometimes the only useful filter: a spreadsheet
  // and a Word document are both `Document` in the Drive's taxonomy.
  extensions: { type: Array, default: () => [] },
  // What the file is attached to, when it is attached to something. A file
  // picked here keeps its own life in the Drive either way.
  attachedTo: { type: Object, default: null },
  // Whether more than one may be taken at once. Off by default because most
  // callers write into a single field, where the second would replace the
  // first.
  multiple: { type: Boolean, default: false },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['picked'])

const uploads = useUploads()

const tab = ref(0)
const error = ref('')
const library = ref(null)

const chooser = ref(null)

//: Said under the control rather than after the upload — §D3. Empty on a site
//: whose bytes go straight to storage.
const ceiling = ceilingNote()

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

/**
 * What there is to choose from — §B1.
 *
 * `place: 'all'` and not the root folder: almost every file in a workspace is
 * an attachment and lives in `Home/Attachments`, so a picker that opened at
 * the root would open on almost nothing.
 *
 * Flat on purpose, which is why folders are dropped rather than shown — you
 * cannot attach one — and search is how you reach into one.
 */
const source = computed(() => fileSource({
  place: 'all',
  kind: props.kind,
  keep: (one) => !one.is_folder && allowed(one),
  empty: {
    icon: 'lucide-folder-open',
    title: __('Nothing to choose from'),
    description: props.kind
      ? __('No {0} files here yet — upload one instead.', [labelForKind(props.kind).toLowerCase()])
      : __('No files here yet — upload one instead.'),
  },
}))

async function choose(file) {
  // Picking, when the picker is on a record, has to end where uploading ends:
  // attached. The server writes a second row pointing at the same object rather
  // than moving the file, because the file being picked is usually already
  // attached to something else.
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
 * Onto the shell's queue rather than awaited here — §D3. It used to be a
 * `putFile` per file with a percentage on the button, so attaching a 200 MB
 * video meant sitting in front of a dialog that could not be closed while it
 * went. The queue is serial, survives navigating away, keeps a failure with a
 * Retry beside it rather than toasting it, and counts in one place wherever
 * the upload was started.
 *
 * What the caller loses is the file arriving before the dialog shuts, which
 * is why `then` exists: the field fills when the bytes land.
 */
function send(...chosenFiles) {
  error.value = ''
  const list = usable(chosenFiles.flat().filter(Boolean))
  if (!list.length) return

  const { good, why } = withinCeiling(list)
  if (why) error.value = why
  if (!good.length) return

  uploads.add(good, {
    attachTo: props.attachedTo,
    then: (made) => emit('picked', made),
  })
  open.value = false
}

function chosen(event) {
  const list = Array.from(event.target?.files || [])
  // So choosing the same file twice in a row still fires `change`.
  if (chooser.value) chooser.value.value = ''
  send(list)
}

/**
 * Refuse what the caller cannot take, before anything is uploaded. `accept` on
 * the input is a hint the file dialog may ignore and a drop ignores entirely.
 */
function usable(list) {
  const good = list.filter((one) => allowed({ file_name: one.name }))
  if (good.length < list.length) {
    error.value = __('Only {0} files can go here.', [
      props.extensions.map((one) => `.${one}`).join(', '),
    ])
  }
  return good
}


// Loaded when the dialog opens rather than on mount: a picker behind every
// Attach field on a form would be one request per field on every record.
watch(open, (showing) => {
  if (showing) {
    error.value = ''
    // `reset` and not `read`: reopened rather than remounted, so the frame
    // still holds whatever was typed in it last time.
    library.value?.reset()
  }
})
</script>

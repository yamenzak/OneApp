<!--
  Attach a file: upload one, or choose one that is already here.

  The component this whole arc was for. Before it there were five separate
  upload surfaces — the record's Meta tab, the attachment gallery, every Attach
  field, the mail composer — and none of them could pick something the
  workspace already had, so the same drawing was uploaded four times under four
  names.

  **Upload writes into the Drive and then picks the result**, which is the
  sentence that makes this one path rather than two. There is no second store
  and no "attached but not in the Drive": a file is a `File` row, and where it
  came from is not a property of it.
-->
<template>
  <Dialog v-model="open" title="Attach a file" size="3xl">
    <template #default>
      <Tabs v-model="tab" :tabs="TABS">
        <template #tab-panel="{ tab: current }">
          <div v-if="current.value === 'upload'" class="py-6">
            <!-- The upload carries where it is going, so a file uploaded
                 here is attached by the same code path Frappe's own uploader
                 uses — there is no second way for a file to reach a record. -->
            <FileUploader
              :file-types="fileTypes"
              :private="true"
              :doctype="attachedTo?.doctype"
              :docname="attachedTo?.docname"
              :fieldname="attachedTo?.fieldname"
              @success="uploaded"
            >
              <template #default="{ openFileSelector, uploading, progress }">
                <div class="flex flex-col items-center gap-3 rounded-6 border border-dashed border-outline-gray-2 py-12">
                  <Icon name="lucide-upload-cloud" class="size-8 text-ink-gray-4" />
                  <Button
                    variant="solid"
                    :label="uploading ? `Uploading ${progress}%` : 'Choose a file'"
                    :loading="uploading"
                    @click="openFileSelector"
                  />
                  <p class="text-p-xs text-ink-gray-5">
                    It goes into the workspace's files, and gets attached here.
                  </p>
                </div>
              </template>
            </FileUploader>
          </div>

          <div v-else class="flex min-h-[24rem] flex-col gap-3 py-4">
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
  FileUploader,
  FormControl,
  Icon,
  Skeleton,
  Tabs,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import FileRow from './FileRow.vue'
import { workspace } from '../../lib/workspace'

const TABS = [
  { label: 'Upload', value: 'upload' },
  { label: 'Choose from files', value: 'choose' },
]

const props = defineProps({
  // Narrows both halves: an Attach Image field offers the camera roll on one
  // tab and only images on the other, rather than letting somebody pick a
  // spreadsheet for a cover photo.
  kind: { type: String, default: '' },
  // What the file is attached to, when it is attached to something. A file
  // picked here keeps its own life in the Drive either way.
  attachedTo: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['picked'])

const tab = ref(0)
const files = ref([])
const search = ref('')
const loading = ref(false)
const error = ref('')

const fileTypes = computed(() => (props.kind === 'Image' ? 'image/*' : undefined))

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
    files.value = (found?.files || []).filter((one) => !one.is_folder)
  } catch (e) {
    error.value = e.message || String(e)
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
      error.value = e.message || String(e)
      return
    }
  }

  emit('picked', file)
  open.value = false
}

// The upload already produced a `File` row — the same kind of row the Drive
// lists — so picking it is the whole of what is left to do.
function uploaded(file) {
  emit('picked', file)
  open.value = false
}

// Loaded when the dialog opens rather than on mount: a picker that fetched a
// page of files behind every Attach field on a form would be one request per
// field on every record anybody opened.
watch(open, (showing) => {
  if (showing) {
    search.value = ''
    load()
  }
})
</script>

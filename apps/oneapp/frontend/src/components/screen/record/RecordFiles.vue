<template>
  <div class="flex flex-col gap-3 pt-4">
    <!--
      What is filed against this record, drawn by the Drive's own row.

      Not a list that looks like the Drive's: the same component over the same
      query with one more `where`. A file attached to a record has
      `attached_to_doctype` and a file in a folder has `folder`, and it can have
      both — which is what makes this a filter rather than a second store, and
      what stops this tab being the one that never got the new column.
    -->
    <Button
      v-if="canWrite"
      class="w-full"
      icon-left="lucide-paperclip"
      label="Attach a file"
      @click="picking = true"
    />
    <FilePicker
      v-model="picking"
      :attached-to="{ doctype, docname: name }"
      @picked="reload"
    />

    <LoadingText v-if="loading" text="Loading files" />

    <EmptyState
      v-else-if="!files.length"
      class="!py-8"
      icon="lucide-paperclip"
      title="No files"
      description="Nothing is filed against this one yet."
    />

    <div v-else class="flex flex-col">
      <FileRow
        v-for="file in files"
        :key="file.name"
        :file="file"
        actions
        :can-write="canWrite"
        @open="look"
        @favourite="favourite"
        @share="share"
        @rename="startRename"
        @trash="remove"
      />
    </div>

    <ErrorMessage :message="error" />

    <FilePreview v-model="previewing" :file="chosen" />
    <FileShare v-model="sharing" :file="chosen" />

    <Dialog v-model="renaming" title="Rename">
      <template #default>
        <FormControl v-model="newName" label="Name" @keyup.enter="finishRename" />
      </template>
      <template #actions>
        <Button variant="solid" label="Rename" @click="finishRename" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl, LoadingText } from '@/ui'
import FilePicker from '../../drive/FilePicker.vue'
import FilePreview from '../../drive/FilePreview.vue'
import FileRow from '../../drive/FileRow.vue'
import FileShare from '../../drive/FileShare.vue'
import EmptyState from '../../EmptyState.vue'
import { workspace } from '../../../lib/workspace'
import { errorText } from '../../../lib/errors'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['count'])

const files = ref([])
const doctype = ref('')
const loading = ref(false)
const error = ref('')

const reload = async () => {
  if (!props.name) {
    files.value = []
    return
  }
  loading.value = true
  try {
    const found = await workspace.attachments(props.spaceCode, props.screen, props.name)
    files.value = found?.files || []
    doctype.value = found?.doctype || ''
    // So the panel's Attachments row can say how many without asking again.
    emit('count', files.value.length)
  } finally {
    loading.value = false
  }
}

// Whether the picker is open, and which file the dialogs are about.
const picking = ref(false)
const previewing = ref(false)
const sharing = ref(false)
const renaming = ref(false)
const chosen = ref(null)
const newName = ref('')

const look = (file) => {
  chosen.value = file
  previewing.value = true
}

const share = (file) => {
  chosen.value = file
  sharing.value = true
}

const startRename = (file) => {
  chosen.value = file
  newName.value = file.file_name || ''
  renaming.value = true
}

const run = async (work) => {
  error.value = ''
  try {
    await work()
    await reload()
  } catch (raised) {
    error.value = errorText(raised)
  }
}

const favourite = (file) => run(() => workspace.driveFavourite(file.name, !file.liked))

const finishRename = async () => {
  const title = newName.value.trim()
  if (!title) return
  await run(() => workspace.driveRename(chosen.value.name, title))
  if (!error.value) renaming.value = false
}

// The bin and not a delete. Taking a file off a record used to remove the row
// outright, which meant a misplaced click on the wrong record's Files tab was
// unrecoverable — and the bin exists precisely so that it is not.
const remove = (file) => run(() => workspace.driveTrash([file.name]))

watch(() => props.name, reload, { immediate: true })
</script>

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
    <div v-if="canWrite" class="flex gap-2">
      <Button
        class="flex-1"
        icon-left="lucide-paperclip"
        label="Attach a file"
        @click="picking = true"
      />
      <!--
        The same New menu the Drive has, pointed at this record. A document or
        a sheet made here is attached rather than filed in a folder, which is
        what makes "the project's scope of works" a query — see `useNewFile`.
      -->
      <Dropdown :options="newOptions">
        <Button icon-left="lucide-plus" label="New" tooltip="New file" :loading="making" />
      </Dropdown>
    </div>
    <FilePicker
      v-model="picking"
      multiple
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
        :link="linkFor(file)"
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
import { inject, ref, watch } from 'vue'
import { Button, Dialog, Dropdown, ErrorMessage, FormControl, LoadingText } from '@/ui'
import FilePicker from '../../drive/FilePicker.vue'
import FilePreview from '../../drive/FilePreview.vue'
import FileRow from '../../drive/FileRow.vue'
import FileShare from '../../drive/FileShare.vue'
import EmptyState from '../../EmptyState.vue'
import { workspace } from '../../../lib/workspace'
import { errorText } from '@/lib/runtime/errors'
import { routeFor } from '@/lib/files/files'
import { useNewFile } from '@/composables/useNewFile'
import { RETURN_TO, returnQuery } from '@/lib/screen/returnTo'

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

// The record this tab belongs to, so an editor opened from here can come back.
const came = inject(RETURN_TO, null)

// A file made here belongs to the record rather than to a folder. `doctype` is
// filled by the reload below, so this reads it rather than closing over it.
const { making, options: newOptions, loadTemplates } = useNewFile(
  () => ({ doctype: doctype.value, docname: props.name }),
)

// Whether the picker is open, and which file the dialogs are about.
const picking = ref(false)
const previewing = ref(false)
const sharing = ref(false)
const renaming = ref(false)
const chosen = ref(null)
const newName = ref('')

/**
 * A sheet, a document or a text file opens in its editor; everything else is
 * looked at where it is. Same rule as the Drive, out of the same function —
 * and with the record on it, so the editor's trail leads back here.
 */
const linkFor = (file) => {
  const route = routeFor(file)
  return route ? { ...route, query: returnQuery(came?.value) } : null
}

// The row is a link where there is somewhere to go, so this only ever runs for
// the files that are looked at rather than opened.
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
loadTemplates()
</script>

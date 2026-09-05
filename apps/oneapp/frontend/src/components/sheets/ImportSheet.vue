<template>
  <!--
    A spreadsheet somebody already has, turned into one of ours.

    The file is uploaded as well as read, and that is on purpose: the original
    `.xlsx` stays in the Drive as a file, because for the first few weeks it is
    the thing its owner still trusts. What is parsed is the copy already in the
    browser rather than the one just stored — `validateFile` hands it over, so
    there is no second round trip to fetch back bytes we had.
  -->
  <Dialog v-model="open" title="Import a spreadsheet">
    <template #default>
      <FileUploader
        :file-types="ACCEPTS"
        :private="true"
        :folder="folder || undefined"
        :validate-file="keep"
        @success="parse"
        @failure="failed"
      >
        <template #default="{ openFileSelector, uploading, progress }">
          <div class="flex flex-col items-center gap-3 rounded-6 border border-dashed border-outline-gray-2 py-10">
            <Icon name="lucide-table-2" class="size-8 text-ink-gray-4" />
            <Button
              variant="solid"
              :label="busy || uploading ? state(uploading, progress) : 'Choose a spreadsheet'"
              :loading="busy || uploading"
              @click="openFileSelector"
            />
            <p class="text-p-xs text-ink-gray-5">
              Excel or CSV. The file is kept in Files, and its cells become a
              sheet you can edit here.
            </p>
          </div>
        </template>
      </FileUploader>

      <Alert v-if="error" class="mt-4" theme="red" title="This could not be imported">
        <template #description>{{ error }}</template>
      </Alert>

      <!-- What was left out, said before anybody goes looking for it. A
           quotation missing its last four lines is worse than an import that
           refused, so the number is on screen rather than in a log. -->
      <Alert v-else-if="skipped" class="mt-4" theme="amber" :title="`${skipped} cells were left out`">
        <template #description>
          A sheet holds {{ MAX_CELLS.toLocaleString() }} cells. What fitted is here.
        </template>
      </Alert>
    </template>
  </Dialog>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Alert, Button, Dialog, FileUploader, Icon } from '@/ui'

import { ACCEPTS, fromFile } from '../../lib/sheets/xlsx'
import { MAX_CELLS } from '../../lib/sheets/refs'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

/** Cells per request. Twenty thousand in one body is a two-megabyte POST. */
const BATCH = 2000

const props = defineProps({
  /** Where the uploaded file goes, so an import inside a folder stays there. */
  folder: { type: String, default: '' },
})

const open = defineModel({ type: Boolean, default: false })
const router = useRouter()

const chosen = ref(null)
const busy = ref(false)
const error = ref('')
const skipped = ref(0)
const step = ref('')

function state(uploading, progress) {
  if (uploading) return `Uploading ${progress}%`
  return step.value || 'Working…'
}

/**
 * Keep the file, and refuse the ones this cannot read.
 *
 * `validateFile` is the only place frappe-ui's uploader hands the `File` over
 * before it goes to the server, and refusing here is refusing before anything
 * is stored — which is the right moment to say "that is a Numbers file".
 */
function keep(file) {
  error.value = ''
  skipped.value = 0
  if (!/\.(xlsx|xlsm|csv)$/i.test(file.name)) {
    return new Error('Only .xlsx, .xlsm and .csv files can be imported.')
  }
  chosen.value = file
  return null
}

async function parse(uploaded) {
  if (!chosen.value) return
  busy.value = true
  error.value = ''
  try {
    step.value = 'Reading…'
    const read = await fromFile(chosen.value)
    skipped.value = read.skipped

    if (!read.cells.length) {
      error.value = 'There is nothing in that file to import.'
      return
    }

    step.value = 'Making the sheet…'
    const title = (uploaded?.file_name || chosen.value.name).replace(/\.[^.]+$/, '')
    const made = await workspace.sheetMake({ title, folder: props.folder || '' })

    // The new sheet has one tab called Sheet1. The first imported tab is that
    // one renamed; the rest are added. Renaming rather than adding-and-deleting
    // keeps a sheet from ever having a tab nobody asked for.
    const [first, ...rest] = read.tabs
    if (first.tab_name !== 'Sheet1') await workspace.sheetRenameTab(made.name, 'Sheet1', first.tab_name)
    for (const tab of rest) await workspace.sheetAddTab(made.name, tab.tab_name)

    for (let at = 0; at < read.cells.length; at += BATCH) {
      step.value = `Writing ${Math.min(at + BATCH, read.cells.length).toLocaleString()} of ${read.cells.length.toLocaleString()} cells…`
      await workspace.sheetWrite(made.name, read.cells.slice(at, at + BATCH))
    }

    open.value = false
    router.push({ name: 'Sheet', params: { name: made.name } })
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    busy.value = false
    step.value = ''
  }
}

function failed(raised) {
  error.value = errorText(raised)
}
</script>

<template>
  <!--
    A spreadsheet somebody already has, turned into one of ours.

    This used to be an uploader, which quietly meant the only spreadsheet you
    could import was one on the machine in front of you. The one you wanted was
    usually already here — attached to a quotation last March by somebody else —
    and the way to import it was to download it and upload it again.

    So it is the ordinary picker, with the ordinary three sources, narrowed to
    the three extensions this can read. Choosing from the library reads the
    bytes back out of the Drive; uploading puts them there first and then reads
    them back the same way. One path, and the original `.xlsx` stays in the
    Drive either way — for the first few weeks it is the thing its owner still
    trusts.
  -->
  <FilePicker
    v-model="open"
    title="Import a spreadsheet"
    :extensions="EXTENSIONS"
    @picked="build"
  />

  <!--
    Never at the same time as the picker: the picker closes on the pick, and
    this opens on the work that follows it. A big workbook is thirty seconds of
    parsing and saving, and a dialog that says which of the two it is on is the
    difference between waiting and refreshing.
  -->
  <Dialog v-model="working" title="Importing">
    <template #default>
      <div class="flex flex-col items-center gap-3 py-8">
        <LoadingIndicator v-if="!error" class="size-6 text-ink-gray-5" />
        <p v-if="!error" class="text-p-sm text-ink-gray-6">{{ step }}</p>

        <Alert v-else class="w-full" theme="red" title="This could not be imported">
          <template #description>{{ error }}</template>
        </Alert>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Alert, Dialog, LoadingIndicator } from '@/ui'

import FilePicker from '../drive/FilePicker.vue'
import { workbookFromFile } from '../../lib/sheets/headless'
import { saveWorkbook } from '../../lib/sheets/store'
import { fetchFile } from '../../lib/files'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

/** What `headless.js` can actually read, as the picker wants them. */
const EXTENSIONS = ['xlsx', 'xlsm', 'csv']

defineProps({
  /** Where an uploaded file goes, so an import inside a folder stays there. */
  folder: { type: String, default: '' },
})

const open = defineModel({ type: Boolean, default: false })
const router = useRouter()

const working = ref(false)
const error = ref('')
const step = ref('')

/**
 * Turn one stored file into a sheet.
 *
 * The bytes are fetched rather than kept from the upload, which costs one
 * download and buys the thing the whole change is for: a file picked from the
 * library and a file just uploaded arrive here identically, so there is one
 * code path instead of a parsed-in-memory one and a fetched one that would
 * drift apart.
 */
async function build(file) {
  working.value = true
  error.value = ''
  try {
    step.value = 'Reading…'
    const bytes = await fetchFile(file)

    // The whole workbook is built in memory before anything is created. A save
    // is the workbook entire — there is no cell endpoint to dribble it through
    // — so a file that turns out to be unreadable leaves no half-made sheet
    // behind in the Drive.
    const read = await workbookFromFile(bytes)
    if (!read.cells) {
      error.value = 'There is nothing in that file to import.'
      return
    }

    step.value = 'Making the sheet…'
    const title = (file.file_name || bytes.name).replace(/\.[^.]+$/, '')
    const made = await workspace.sheetMake({ title, folder: file.folder || '' })

    step.value = `Saving ${read.cells.toLocaleString()} cells…`
    await saveWorkbook(made.name, title, read.payload)

    working.value = false
    router.push({ name: 'Sheet', params: { name: made.name } })
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    step.value = ''
  }
}
</script>

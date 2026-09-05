<template>
  <!--
    One spreadsheet, open.

    A page rather than a screen inside a Space, for the same reason Mail and
    Files are: a sheet belongs to the workspace's file table, not to any one
    Space. It is reached from the Drive, from an attachment on a record, or
    from a link somebody sent — and none of those knows which Space you were in.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center gap-1">
      <Breadcrumbs :items="crumbs" />
      <!--
        Renaming, here rather than only in the Drive. A new sheet is called
        "Untitled sheet", and the first thing anybody does with one is give it
        a name — sending them back to the file list to do it is the sort of gap
        that only shows up when you try to pick one of four sheets out of a
        dropdown and every one of them is called the same thing.
      -->
      <Button
        v-if="sheet.canWrite.value && !sheet.loading.value"
        icon="lucide-pencil"
        label="Rename this sheet"
        tooltip="Rename this sheet"
        variant="ghost"
        @click="startRename"
      />
    </nav>

    <div class="flex shrink-0 items-center gap-2">
      <!-- Whether what is on screen is what is stored. Three states and no
           spinner: a spinner beside a grid somebody is typing into is noise,
           and the only one that matters is the one that says it failed. -->
      <Tooltip v-if="sheet.saveError.value" :text="sheet.saveError.value">
        <Badge theme="red" variant="subtle" label="Not saved" />
      </Tooltip>
      <Tooltip v-if="downloadError" :text="downloadError">
        <Badge theme="red" variant="subtle" label="Download failed" />
      </Tooltip>
      <span v-else-if="sheet.dirty.value || sheet.saving.value" class="text-p-xs text-ink-gray-5">
        Saving…
      </span>
      <span v-else-if="sheet.canWrite.value" class="text-p-xs text-ink-gray-5">Saved</span>

      <!-- A template badge rather than a menu item that says it: whether this
           is the sheet everybody starts from is worth seeing without opening
           anything. -->
      <Badge
        v-if="sheet.isTemplate.value"
        theme="blue"
        variant="subtle"
        label="Template"
      />
      <Dropdown :options="downloads">
        <Button
          icon-left="lucide-download"
          icon-right="lucide-chevron-down"
          label="Download"
          tooltip="Download"
          variant="ghost"
          :loading="exporting"
        />
      </Dropdown>
      <Dropdown :options="menu">
        <Button icon="lucide-more-horizontal" label="More" tooltip="More" variant="ghost" />
      </Dropdown>
    </div>
  </PageHeader>

  <div class="flex h-full min-h-0 flex-col">
    <div v-if="sheet.loading.value" class="flex flex-col gap-2 p-5">
      <Skeleton v-for="n in 10" :key="n" class="h-7 w-full" />
    </div>

    <Alert v-else-if="sheet.error.value" class="m-5" theme="red" title="This sheet could not be opened">
      <template #description>{{ sheet.error.value }}</template>
    </Alert>

    <template v-else>
      <SheetToolbar :sheet="sheet" @name-range="naming = true" />

      <!-- Read-only is said once, here, rather than by every control being
           quietly absent: a person who cannot work out why nothing types is a
           support ticket. -->
      <Alert
        v-if="!sheet.canWrite.value"
        class="mx-4 mt-3"
        theme="gray"
        title="You can read this sheet but not change it"
      >
        <template #description>Ask whoever shared it for edit access.</template>
      </Alert>

      <SheetGrid ref="grid" :sheet="sheet" />

      <!--
        The printer's copy, built rather than captured. The grid windows its
        rows, so printing the page itself prints whichever forty are in the
        DOM — this is the used range as a plain table, in an iframe, which is
        the same shape `PrintDialog` uses for a record's print format.
      -->
      <iframe
        ref="printer"
        title="Print preview"
        class="pointer-events-none fixed h-0 w-0 border-0 opacity-0"
        aria-hidden="true"
      />

      <TabStrip
        :sheet="sheet"
        @add="sheet.addTab"
        @rename="sheet.renameTab"
        @remove="sheet.removeTab"
      />
    </template>
  </div>

  <Dialog v-model="renaming" title="Rename">
    <template #default>
      <FormControl v-model="newName" type="text" label="Name" @keydown.enter="finishRename" />
    </template>
    <template #actions>
      <Button variant="solid" label="Rename" :loading="busy" @click="finishRename" />
    </template>
  </Dialog>

  <Dialog v-model="naming" title="Name this range">
    <template #default>
      <!-- What a named range is for, said where somebody is naming one. It is
           the contract between a sheet and the document it feeds, and nothing
           else in the product explains that. -->
      <p class="mb-3 text-p-sm text-ink-gray-6">
        A named range is what a record reads back. Give
        {{ sheet.active.value }}!{{ selection }} a name, and a document can fill
        its rows from it.
      </p>
      <FormControl
        v-model="label"
        type="text"
        label="Name"
        placeholder="LineItems"
        @keydown.enter="nameIt"
      />

      <div v-if="sheet.ranges.value.length" class="mt-5 flex flex-col gap-1">
        <FormLabel label="Already named" />
        <div
          v-for="range in sheet.ranges.value"
          :key="range.label"
          class="flex items-center justify-between gap-2 rounded-4 px-2 py-1 hover:bg-surface-gray-2"
        >
          <Button
            variant="ghost"
            :label="`${range.label} — ${range.tab}!${range.ref}`"
            @click="goTo(range)"
          />
          <Button
            icon="lucide-x"
            label="Remove this name"
            tooltip="Remove this name"
            variant="ghost"
            @click="sheet.forgetRange(range.label)"
          />
        </div>
      </div>
    </template>
    <template #actions>
      <Button variant="solid" label="Name it" :loading="busy" @click="nameIt" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Alert, Badge, Breadcrumbs, Button, Dialog, Dropdown, FormControl, FormLabel, PageHeader,
  Skeleton, Tooltip,
} from '@/ui'

import SheetGrid from '../components/sheets/SheetGrid.vue'
import SheetToolbar from '../components/sheets/SheetToolbar.vue'
import TabStrip from '../components/sheets/TabStrip.vue'
import { useSheet } from '../composables/useSheet'
import { workspace } from '../lib/workspace'
import { errorText } from '../lib/errors'
import { formatRange } from '../lib/sheets/refs'
import { toHtml } from '../lib/sheets/printing'

const props = defineProps({
  name: { type: String, required: true },
})

const router = useRouter()
const sheet = useSheet(props.name)
const grid = ref(null)
const printer = ref(null)
const naming = ref(false)
const renaming = ref(false)
const newName = ref('')
const label = ref('')
const busy = ref(false)
const exporting = ref(false)
const downloadError = ref('')

sheet.load()

const crumbs = computed(() => [
  { label: 'Files', route: { name: 'Drive' } },
  { label: sheet.title.value || 'Sheet' },
])

const selection = computed(() => formatRange(sheet.area.value))

async function nameIt() {
  const wanted = label.value.trim()
  if (!wanted) return
  busy.value = true
  try {
    await sheet.nameSelection(wanted)
    label.value = ''
  } finally {
    busy.value = false
  }
}

const menu = computed(() => [
  { label: 'Print this tab', icon: 'lucide-printer', onClick: print },
  ...(sheet.canWrite.value
    ? [{
        // A template is a sheet with a flag on it, so this is the whole
        // feature — see `oneapp_core/sheets/templates.py`.
        label: sheet.isTemplate.value ? 'Stop using as a template' : 'Use as a template',
        icon: sheet.isTemplate.value ? 'lucide-bookmark-minus' : 'lucide-bookmark-plus',
        onClick: () => sheet.setTemplate(!sheet.isTemplate.value),
      }]
    : []),
  // `onClick` and not `to`: a `{ icon, to }` literal is what the shell's
  // navigation entries look like, and `test_navigation_is_declared_in_one_place`
  // is right to insist those live in `lib/nav.js`. This is a menu item on one
  // page, which is a different thing wearing the same shape.
  {
    label: 'Show in Files',
    icon: 'lucide-folder-open',
    onClick: () => router.push({ name: 'Drive' }),
  },
])

/**
 * Print the tab on screen.
 *
 * The document is written into the iframe and printed from there, so nothing
 * about the app's own stylesheet or the shell's chrome can reach it.
 */
function print() {
  const frame = printer.value
  if (!frame) return
  frame.srcdoc = toHtml({
    cells: [...sheet.book.value.cells.values()],
    tab: sheet.active.value,
    title: sheet.title.value,
  })
  frame.onload = () => {
    frame.contentWindow?.focus()
    frame.contentWindow?.print()
  }
}

function startRename() {
  newName.value = sheet.title.value
  renaming.value = true
}

async function finishRename() {
  const wanted = newName.value.trim()
  if (!wanted || wanted === sheet.title.value) {
    renaming.value = false
    return
  }
  busy.value = true
  try {
    await workspace.driveRename(props.name, wanted)
    sheet.title.value = wanted
    renaming.value = false
  } finally {
    busy.value = false
  }
}

function goTo(range) {
  sheet.goToRange(range)
  naming.value = false
}

const downloads = computed(() => [
  { label: 'Excel workbook (.xlsx)', icon: 'lucide-table-2', onClick: asExcel },
  { label: 'This tab as CSV', icon: 'lucide-file-text', onClick: asCsv },
])

/**
 * The CSV is the server's — one tab, values, no formats, and the same bytes a
 * share link hands a stranger. Nothing here has to build it.
 */
function asCsv() {
  window.location.href =
    `/api/method/oneapp.oneapp_core.sheets.download?name=${encodeURIComponent(props.name)}` +
    `&tab=${encodeURIComponent(sheet.active.value)}`
}

/**
 * The workbook is the browser's, because the browser is the only side that has
 * the formulas and the formats — the server stores `raw` and never reads it.
 * `exceljs` is a 900KB dependency and is imported here, on the press, so a
 * grid that nobody exports never loads it.
 */
async function asExcel() {
  exporting.value = true
  try {
    const { toBlob } = await import('../lib/sheets/xlsx')
    const blob = await toBlob({
      cells: [...sheet.book.value.cells.values()],
      tabs: sheet.tabs.value,
      title: sheet.title.value,
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${sheet.title.value || 'sheet'}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } catch (raised) {
    downloadError.value = errorText(raised)
  } finally {
    exporting.value = false
  }
}

// What is typed and not yet sent must not be lost by a click on a link. The
// queue settles after 700ms; leaving the page inside that window is the one
// moment it can be.
watch([naming, renaming], ([a, b]) => { if (!a && !b) grid.value?.focus?.() })
onBeforeUnmount(() => sheet.flush())
</script>

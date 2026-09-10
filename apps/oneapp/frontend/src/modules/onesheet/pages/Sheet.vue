<template>
  <!--
    One spreadsheet, open.

    A page rather than a screen inside a Space, for the same reason Mail and
    Files are: a sheet belongs to the workspace's file table, not to any one
    Space. It is reached from the Drive, from an attachment on a record, or
    from a link somebody sent — and none of those knows which Space you were in.

    There is no `PageHeader` here, and that is the point. The editor is
    Frappe's, vendored whole (`lib/sheets/VENDORED.md`), and it brings its own
    identity bar, formula bar, toolbar and tab strip — four rows of chrome that
    a fifth would only crowd. What OneSpace has to say about a sheet that a
    standalone spreadsheet cannot — that it is a file, that it can be the one
    everybody starts from — goes into the editor's own File menu instead.
  -->
  <!-- The editor and, beside it, what this workbook reads. The rail is the
       document editor's, unchanged: a workbook reads the same set of records
       and needs the same four things of them —
       `shared/components/RecordPanel.vue`. What differs is only where a
       click puts the answer, which here is a `RECORD()` formula in the cell
       you are standing on. -->
  <div class="flex h-full min-h-0">
    <SheetEditor
      ref="editor"
      :id="name"
      :host-menu="hostMenu"
      class="min-w-0 flex-1"
      @close="close"
    />

    <RecordPanel
      v-if="showRecords"
      :name="name"
      :sources="about"
      :values="values"
      :busy="reading"
      :read-at="readAt"
      :said="__('The workbook will read this record, and RECORD() can name its fields.')"
      can-write
      @insert-field="insertField"
      @insert-table="insertTable"
      @refresh="readRecords"
      @changed="about = $event"
      @close="showRecords = false"
    />
  </div>

  <TemplatePicker
    v-model="picking"
    :rows="templates"
    icon="lucide-table-2"
    :said="__('Its sheets are added to this workbook as new tabs. Nothing here is written over.')"
    @pick="fromTemplate"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import SheetEditor from '@/modules/onesheet/components/editor/index.vue'
import RecordPanel from '@/shared/components/RecordPanel.vue'
import TemplatePicker from '@/modules/onestorage/components/TemplatePicker.vue'
import { block, said, setTables } from '@/modules/onesheet/lib/services/recordFields'
import { workspace } from '@/shared/lib/workspace'
import { cameFrom } from '@/modules/onespace/lib/screen/returnTo'
import { notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  name: { type: String, required: true },
})

const router = useRouter()
const route = useRoute()

// The record this sheet was opened from, when it was. See
// `lib/screen/returnTo.js` — a sheet made off a quotation's line items used to
// close to the Drive's root, with the quotation gone.
const back = computed(() => cameFrom(route))

// Read once, on open. The editor owns the workbook and never tells anybody
// about the File behind it, so this is the one thing the host has to ask for
// itself — and it changes only when somebody presses the menu item below.
const isTemplate = ref(false)
workspace
  .sheetTemplates()
  .then((rows) => { isTemplate.value = (rows || []).some((row) => row.name === props.name) })
  .catch(() => {})

/**
 * The record and table this sheet feeds, when it feeds one.
 *
 * A sheet made from a quotation's line items is bound to them, and the person
 * pricing the job is *in the sheet* — so the send belongs here as well as on
 * the record. Two doors, one press: it stays a deliberate act because a
 * quotation is a commitment and a rate edited at six o'clock must not move a
 * number somebody agreed to.
 */
const bound = ref(null)

workspace
  .sheetBoundTo(props.name)
  .then((found) => { bound.value = found?.reference_doctype ? found : null })
  .catch(() => {})

/*
 * The records this sheet *reads*, which are not the table it feeds.
 *
 * `bound` above is the outward leg — the child table these rows go back to.
 * This is the inward one: the set `RECORD()` resolves against. A workbook
 * naming none asks for nothing, so every ordinary sheet pays one call that
 * answers immediately.
 *
 * Asked on open and again when somebody presses Refresh, which is the whole
 * freshness contract — `lib/services/recordFields.js` says why it cannot be
 * anything cleverer.
 */
const about = ref([])
const reading = ref(false)
const readAt = ref(null)
const values = ref({})

// The rail is open when there is something in it. A workbook that reads
// nothing is most of them, and a panel saying so on every open is a panel
// everybody closes.
const showRecords = ref(false)

workspace
  .sheetRecordFields(props.name, [])
  .then((found) => {
    about.value = found?.sources || []
    showRecords.value = !!about.value.length
    // And read them, so the rail's footer says when rather than nothing and
    // each field shows what it would insert. The editor does its own read
    // once the workbook is in memory; this is the one that fills the rail,
    // and it costs nothing extra for a workbook whose cells name no records
    // — `resolveRecordFields` answers without a request when there is
    // nothing to ask about.
    if (about.value.length) readRecords()
  })
  .catch(() => {})

// The editor reads on its own once the workbook is in memory; this is the
// second ask, the one somebody presses an hour later — and the one the rail
// presses after a source is added.
async function readRecords() {
  reading.value = true
  try {
    await editor.value?.refreshRecords(about.value)
    // Read back out of the cache the engine resolves through, so the rail's
    // previews and the cells agree by construction rather than by two
    // requests that happen to say the same thing.
    values.value = said()
    readAt.value = new Date()
  } finally {
    reading.value = false
  }
}

/**
 * A field, as the formula that reads it.
 *
 * The keyed form, always, even for the first source: `RECORD("grand_total")`
 * is shorter and means "whatever this workbook is mainly about", which is a
 * different and vaguer thing than what somebody just clicked. A formula that
 * names its source survives a second record being added above it.
 */
function insertField(one) {
  editor.value?.putFormula(`=RECORD("${one.source}", "${one.field}")`)
}

/**
 * A child table, as a block of cells from the one you are standing on.
 *
 * A header row of labels and then a `RECORDROW()` per cell — formulas
 * rather than a paste, which is the whole difference between this and
 * exporting a CSV. Every cell re-reads on Refresh, so a line whose rate
 * changed changes here; what is fixed is the block's *height*, the lines
 * that existed when it was written, which is the same bargain a token in a
 * document makes about its field.
 *
 * The rows have to be in hand to know how many there are, so this asks
 * first when the schedule is not in the cache yet.
 */
async function insertTable(one) {
  let found = block(one.source, one.table)
  if (!found) {
    // Nothing in this workbook names the table yet, so nothing fetched it.
    // One request, shaped exactly like the ones the formulas will make.
    const answer = await workspace.sheetRecordFields(props.name, [{
      source: one.source, table: one.table, fields: one.columns || [],
    }])
    setTables(answer?.tables)
    found = block(one.source, one.table)
  }
  if (!found) return

  const columns = found.columns || []
  const cells = [columns.map((c) => c.label)]
  ;(found.values || []).forEach((_line, at) => {
    cells.push(columns.map(
      (c) => `=RECORDROW("${one.source}", "${one.table}", ${at + 1}, "${c.fieldname}")`,
    ))
  })
  editor.value?.putBlock(cells)
}

function sendRows() {
  const feed = bound.value
  if (!feed) return null
  return workspace.sheetPull(props.name, {
    label: feed.label,
    doctype: feed.reference_doctype,
    docname: feed.reference_name,
    into: feed.into,
  })
}

/*
 * Templates, and what picking one does.
 *
 * They used to be rows in the Drive's New menu. Wrong place twice over: New is
 * a menu of *kinds*, and a workspace's own files in it made the kinds hard to
 * find; and the moment you want a template is the moment you are looking at a
 * grid, not the moment you decided to make one.
 *
 * And it loads *into this workbook*, as new tabs, rather than opening the
 * template as a separate file. That is the whole point of it. A sheet bound to
 * a record's child table is that record's workbook: somebody pricing a
 * quotation opens its line items here, loads their estimator beside them, does
 * the working and fills the bound tab from it. The working has to be in the
 * same book — so a formula can reach across to it, and so it is still there
 * the next time that quotation is repriced. A separate file would be a
 * calculation nobody can find again.
 *
 * Nothing already here is written over; see `useTemplateInsert`.
 *
 * Fetched when the dialog is first opened rather than on mount: most sheets
 * are opened to work in, and a query for a list nobody will look at is a query
 * every open pays for.
 */
const editor = ref(null)
const picking = ref(false)
const templates = ref([])

watch(picking, (open) => {
  if (!open || templates.value.length) return
  workspace.sheetTemplates()
    .then((found) => { templates.value = found || [] })
    .catch(() => { templates.value = [] })
})

async function fromTemplate(row) {
  const done = await editor.value?.insertTemplate(row.name)
  if (!done?.added?.length) return

  notifySuccess(
    done.added.length === 1
      ? __('{0} was added as a tab.', [done.added[0]])
      : __('{0} tabs were added.', [done.added.length]),
    // Said rather than dropped quietly: a template with a chart in it comes in
    // without the chart, and finding that out by looking for it is worse than
    // being told.
    done.left.length
      ? { description: __('Charts, pivots and named ranges did not come across.') }
      : {},
  )
}

const hostMenu = computed(() => [{
  group: __('This sheet'),
  options: [
    {
      label: __('Load a template'),
      icon: 'lucide-bookmark',
      onClick: () => { picking.value = true },
    },
    // The rows go back to the record this sheet was made from. Only where the
    // person may write that record, and never where the table has been locked
    // — after a lock the document is the record and the sheet is history.
    ...(bound.value && bound.value.may_write && bound.value.status !== 'Locked'
      ? [{
        label: __('Send these rows to {0}', [bound.value.title]),
        icon: 'lucide-corner-up-left',
        onClick: () => sendRows(),
      }]
      : []),
    // Always offered, unlike the old "Read X again" it replaces: a workbook
    // that reads nothing yet is exactly the one somebody opens this to give
    // a record to, and the rail carries its own Refresh.
    {
      label: showRecords.value ? __('Hide the records') : __('Records'),
      icon: 'lucide-link',
      onClick: () => { showRecords.value = !showRecords.value },
    },
    {
      // "Start from the last one", which is how a workspace prices its third
      // job. The document editor has had this since it was written; the
      // sheet's Rename is *not* the same gap, because a sheet's title is an
      // editable field in its own header and a document's is a breadcrumb.
      label: __('Duplicate'),
      icon: 'lucide-copy',
      onClick: () => duplicate(),
    },
    {
      // A template is a sheet with a flag on it, so this is the whole feature
      // — see `onesheet/templates.py`.
      label: isTemplate.value ? __('Stop using as a template') : __('Use as a template'),
      icon: isTemplate.value ? 'lucide-bookmark-minus' : 'lucide-bookmark-plus',
      onClick: async () => {
        const next = !isTemplate.value
        await workspace.sheetSetTemplate(props.name, next)
        isTemplate.value = next
      },
    },
    // `onClick` and not `to`: a `{ icon, to }` literal is what the shell's
    // navigation entries look like, and `test_navigation_is_declared_in_one_place`
    // is right to insist those live in `lib/nav.js`. This is a menu item on one
    // page, which is a different thing wearing the same shape.
    ...(back.value
      ? [{ label: __('Back to {0}', [back.value.label]), icon: 'lucide-arrow-left', onClick: () => close() }]
      : []),
    { label: __('Show in Files'), icon: 'lucide-folder-open', onClick: () => showInFiles() },
  ],
}])

function showInFiles() {
  router.push({ name: 'Drive' })
}

/** Another sheet like this one, and open it — a copy you cannot see is a
 *  copy you make twice. */
async function duplicate() {
  const made = await workspace.sheetDuplicate(props.name, '')
  if (made?.name) router.push(`/one/sheets/${made.name}`)
}

// Closing goes where you came from, and only falls back to the Drive when this
// sheet was reached from there in the first place.
function close() {
  if (back.value) router.push(back.value.path)
  else showInFiles()
}
</script>

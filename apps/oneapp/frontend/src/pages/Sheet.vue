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
  <SheetEditor :id="name" :host-menu="hostMenu" @close="close" />
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import SheetEditor from '../components/sheets/editor/index.vue'
import { workspace } from '../lib/workspace'
import { cameFrom } from '@/lib/screen/returnTo'

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

const hostMenu = computed(() => [{
  group: 'This sheet',
  options: [
    // The rows go back to the record this sheet was made from. Only where the
    // person may write that record, and never where the table has been locked
    // — after a lock the document is the record and the sheet is history.
    ...(bound.value && bound.value.may_write && bound.value.status !== 'Locked'
      ? [{
        label: `Send these rows to ${bound.value.title}`,
        icon: 'corner-up-left',
        onClick: () => sendRows(),
      }]
      : []),
    {
      // A template is a sheet with a flag on it, so this is the whole feature
      // — see `oneapp_core/sheets/templates.py`.
      label: isTemplate.value ? 'Stop using as a template' : 'Use as a template',
      icon: isTemplate.value ? 'bookmark-minus' : 'bookmark-plus',
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
      ? [{ label: `Back to ${back.value.label}`, icon: 'arrow-left', onClick: () => close() }]
      : []),
    { label: 'Show in Files', icon: 'folder-open', onClick: () => showInFiles() },
  ],
}])

function showInFiles() {
  router.push({ name: 'Drive' })
}

// Closing goes where you came from, and only falls back to the Drive when this
// sheet was reached from there in the first place.
function close() {
  if (back.value) router.push(back.value.path)
  else showInFiles()
}
</script>

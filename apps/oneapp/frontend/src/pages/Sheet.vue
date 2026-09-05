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
  <SheetEditor :id="name" :host-menu="hostMenu" @close="showInFiles" />
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import SheetEditor from '../components/sheets/editor/index.vue'
import { workspace } from '../lib/workspace'

const props = defineProps({
  name: { type: String, required: true },
})

const router = useRouter()

// Read once, on open. The editor owns the workbook and never tells anybody
// about the File behind it, so this is the one thing the host has to ask for
// itself — and it changes only when somebody presses the menu item below.
const isTemplate = ref(false)
workspace
  .sheetTemplates()
  .then((rows) => { isTemplate.value = (rows || []).some((row) => row.name === props.name) })
  .catch(() => {})

const hostMenu = computed(() => [{
  group: 'This sheet',
  options: [
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
    { label: 'Show in Files', icon: 'folder-open', onClick: () => showInFiles() },
  ],
}])

function showInFiles() {
  router.push({ name: 'Drive' })
}
</script>

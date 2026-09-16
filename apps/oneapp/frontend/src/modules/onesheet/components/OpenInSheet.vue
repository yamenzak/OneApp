<template>
  <!--
    The sheet these rows are priced in — this table's own, made on the first
    press and reopened on every one after.

    It opened on its own page once, and a route change took the record away and
    made "come back to it" a feature — `returnTo`, a crumb, a query parameter —
    instead of a thing that needed no feature at all. Pricing a child table is
    something you do *while looking at the record*.

    So it became a dialog, and now it is a **window**, which is the same
    argument one turn further: a dialog is modal, so it took the record away
    too — you could see it behind the scrim and not reach it. A window sits
    over the record and leaves it working, which is the whole of what the
    dialog was chosen for and the half it could not deliver.
    `docs/DESKTOP.md` stage 6.

    Nothing is drawn here any more. The window is `FileWindows`, the same one
    a sheet opened from OneCloud gets — `onestorage/lib/editing.js` — because
    a sheet open beside a record and a sheet open beside a folder are the same
    sheet in the same frame, and two of them would be two things to keep in
    step.
  -->
  <OpenIn
    brand="onesheet"
    slot-name="open-in-sheet"
    :tooltip="from
      ? `Open ${from.sheet_title}, where these rows are priced`
      : 'Price these rows in a spreadsheet, then send them back'"
    :loading="making"
    @open="open"
  />
</template>

<script setup>
import { ref } from 'vue'

import OpenIn from '@/shared/components/brand/OpenIn.vue'
import { openFile } from '@/modules/onestorage/lib/editing'
import { workspace } from '@/shared/lib/workspace'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  into: { type: String, required: true },
  /** The standing `Sheet Feed`, when this table has one. */
  from: { type: Object, default: null },
})

const making = ref(false)

async function open() {
  making.value = true
  try {
    const made = await workspace.sheetFromTable({
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
    // As a file, because that is what it is: `sheet_from_table` makes a `File`
    // like every other sheet, and the window opens whatever kind it is handed.
    openFile({
      name: made.name,
      file_name: made.sheet_title || props.from?.sheet_title || made.title || '',
      custom_kind: 'Sheet',
    })
  } finally {
    making.value = false
  }
}
</script>

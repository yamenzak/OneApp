<template>
  <!--
    The sheet these rows are priced in — this table's own, made on the first
    press and reopened on every one after.

    It opens in a dialog rather than on its own page, which is what the other
    two seams do and is the reason this changed: pricing a child table is
    something you do *while looking at the record*, and a route change took the
    record away and made "come back to it" a feature — `returnTo`, a crumb, a
    query parameter — instead of a thing that needed no feature at all.

    The editor brings its own bar, its own mark and its own way out, so the
    dialog is `bare`: a second header above it would say the file's name twice.
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

  <Dialog v-model="showing" bare size="7xl">
    <template #default>
      <!--
        Tall and fixed rather than sized to the grid: a spreadsheet has no
        natural height, and one that grew with its rows would resize the dialog
        every time somebody pasted.
      -->
      <div
        v-if="opened"
        class="flex h-[82vh] min-h-0 flex-col overflow-hidden rounded-6"
        data-slot="sheet-dialog"
        :data-sheet="opened"
      >
        <SheetEditor :key="opened" :id="opened" :host-menu="[]" @close="showing = false" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref } from 'vue'

import { Dialog } from '@/ui'
import OpenIn from '../brand/OpenIn.vue'
import SheetEditor from './editor/index.vue'
import { workspace } from '@/lib/workspace'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  into: { type: String, required: true },
  /** The standing `Sheet Feed`, when this table has one. */
  from: { type: Object, default: null },
})

const making = ref(false)
const showing = ref(false)

//: The sheet on screen. Held rather than read from `from`, because the first
//: press is what creates it and `from` does not know about it until the record
//: is read again.
const opened = ref('')

async function open() {
  making.value = true
  try {
    const made = await workspace.sheetFromTable({
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
    opened.value = made.name
    showing.value = true
  } finally {
    making.value = false
  }
}
</script>

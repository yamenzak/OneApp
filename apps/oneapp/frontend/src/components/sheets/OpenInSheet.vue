<template>
  <!--
    The sheet these rows are priced in — this table's own, made on the first
    press and reopened on every one after.

    It says which sheet once there is one. Two controls that both mentioned a
    sheet, sitting side by side, was the confusion this replaces: an "open" and
    a "fill" read as two features rather than as two ends of one round trip,
    and once a table has exactly one sheet the second question — which one? —
    is already answered. Choosing a different one is in the overflow, where a
    once-per-table act belongs.
  -->
  <Button
    data-slot="open-in-sheet"
    icon-left="lucide-table-2"
    variant="ghost"
    size="sm"
    :label="label"
    :tooltip="from
      ? 'Open the sheet these rows are priced in'
      : 'Price these rows in a spreadsheet, then send them back'"
    :loading="making"
    @click="open"
  />
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'

import { Button } from '@/ui'
import { workspace } from '@/lib/workspace'
import { RETURN_TO, returnQuery } from '@/lib/screen/returnTo'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  into: { type: String, required: true },
  /** The standing `Sheet Feed`, when this table has one. */
  from: { type: Object, default: null },
})

// Named once there is a name. "Open in a sheet" before, because there is no
// sheet yet and naming one that does not exist is a lie.
const label = computed(() => (props.from?.sheet_title
  ? `Open ${props.from.sheet_title}`
  : 'Open in a sheet'))

const router = useRouter()
const making = ref(false)

// The record this was pressed on, so closing the sheet comes back to it rather
// than to the Drive's root.
const came = inject(RETURN_TO, null)

async function open() {
  making.value = true
  try {
    const made = await workspace.sheetFromTable({
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
    router.push({
      name: 'Sheet',
      params: { name: made.name },
      query: returnQuery(came?.value),
    })
  } finally {
    making.value = false
  }
}
</script>

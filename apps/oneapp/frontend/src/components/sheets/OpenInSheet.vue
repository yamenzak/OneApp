<template>
  <!--
    The other direction. `FillFromSheet` reads a sheet into these rows; this
    puts these rows into a sheet — headings from the column labels, the named
    range already drawn round the block, attached to this record.

    Both halves matter and only one of them existed. Using a sheet on a
    quotation used to mean making a blank one, typing the headings by hand
    *exactly* as the child doctype labels them, and naming a range: three
    chances to get it subtly wrong, each discovered at the pull.
  -->
  <Button
    icon-left="lucide-table-2"
    variant="ghost"
    size="sm"
    label="Open in a sheet"
    tooltip="Price these rows in a spreadsheet, then fill them back"
    :loading="making"
    @click="open"
  />
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { Button } from '@/ui'
import { workspace } from '@/lib/workspace'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  into: { type: String, required: true },
})

const router = useRouter()
const making = ref(false)

async function open() {
  making.value = true
  try {
    const made = await workspace.sheetFromTable({
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
    router.push({ name: 'Sheet', params: { name: made.name } })
  } finally {
    making.value = false
  }
}
</script>

<template>
  <!--
    What a row is, in one cell.

    Frappe's list leads with the subject and nothing else competes with it, so
    this is the first column whatever else a person has chosen. The avatar comes
    from the doctype's own image field where it declares one; where it does not,
    Avatar draws initials from the id, which is still a more recognisable mark
    than a blank square.
  -->
  <div class="flex min-w-0 items-center gap-2">
    <Avatar :image="image" :label="String(title || row.name)" shape="square" size="lg" />
    <div class="flex min-w-0 flex-col">
      <span class="truncate text-p-sm text-ink-gray-8">{{ title || row.name }}</span>
      <!-- The id underneath, quietly: it is what a person quotes on the phone
           and never what they read first. Suppressed when the title is the id,
           which is most doctypes without a title field. -->
      <span v-if="title && title !== row.name" class="truncate text-p-xs text-ink-gray-5">
        {{ row.name }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar } from '@/ui'

const props = defineProps({
  row: { type: Object, required: true },
  titleField: { type: String, default: '' },
  imageField: { type: String, default: '' },
})

const title = computed(() => (props.titleField ? props.row[props.titleField] : '') || '')
const image = computed(() => (props.imageField ? props.row[props.imageField] : '') || '')
</script>

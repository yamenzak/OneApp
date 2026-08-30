<template>
  <!--
    Who made this and when it last changed — the question every desk sidebar
    answers, and the one thing on a record that no field carries.

    At the foot of the details rather than at the top: it is what you look for
    second, after the record itself, and a form that opens with its own
    bookkeeping puts the least interesting thing first.
  -->
  <dl class="flex flex-col gap-1 border-t border-outline-gray-1 pt-3 text-p-xs text-ink-gray-5">
    <div v-for="row in rows" :key="row.label" class="flex items-baseline gap-2">
      <dt class="shrink-0">{{ row.label }}</dt>
      <dd class="min-w-0 truncate text-ink-gray-7">{{ row.value }}</dd>
    </div>
  </dl>
</template>

<script setup>
import { computed } from 'vue'
import { dayjsLocal } from '@/ui'

const props = defineProps({
  record: { type: Object, required: true },
})

// "3 days ago" rather than a timestamp, with the timestamp on hover — the same
// call the list's activity column makes, for the same reason: nobody reads a
// record to find out that it is 14:32.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

const rows = computed(() => {
  const found = []
  if (props.record?.owner) {
    found.push({ label: 'Created by', value: props.record.owner })
  }
  if (props.record?.creation) {
    found.push({ label: 'Created', value: when(props.record.creation) })
  }
  // Only when it is not the same event. A record made and never touched says
  // "created" twice otherwise.
  if (props.record?.modified && props.record.modified !== props.record.creation) {
    found.push({
      label: 'Last changed',
      value: [when(props.record.modified), props.record.modified_by]
        .filter(Boolean)
        .join(' by '),
    })
  }
  return found
})
</script>

<template>
  <!--
    One list cell. How a field reads in a list is a different question from how
    it is edited: a Check is a Switch in a form and a tick here, a Select is a
    dropdown there and a coloured badge here.

    The colour comes from the doctype's own `states` where it declares them, and
    from Frappe's word lists otherwise — so a status is not one colour in
    OneSpace and another in the desk.
  -->
  <Badge
    v-if="column.cell === 'badge' && value"
    :theme="valueTheme(value, states)"
    :label="String(value)"
    variant="subtle"
  />

  <span v-else-if="column.cell === 'check'" class="text-ink-gray-7">
    <Icon
      :name="value ? 'lucide-check' : 'lucide-minus'"
      :class="value ? 'size-4 text-ink-green-3' : 'size-4 text-ink-gray-4'"
    />
  </span>

  <Rating v-else-if="column.cell === 'rating'" :model-value="Number(value) || 0" disabled />

  <div v-else-if="column.cell === 'image'" class="flex items-center">
    <Avatar v-if="value" :image="value" :label="String(value)" shape="square" size="sm" />
    <span v-else class="text-p-sm text-ink-gray-4">—</span>
  </div>

  <div v-else-if="column.cell === 'color'" class="flex items-center gap-2">
    <span
      v-if="value"
      class="size-3 shrink-0 rounded-full border border-outline-gray-2"
      :style="{ backgroundColor: value }"
    />
    <span class="truncate text-p-sm text-ink-gray-7">{{ value || '—' }}</span>
  </div>

  <!--
    A link is a record. The server resolves the ids on a page to their title and
    image in one query per column, so a cell shows what a person recognises
    rather than what the database stores — and falls back to the id when the
    target is one they may not read, which is the truthful thing to show.
  -->
  <RecordChip v-else-if="column.cell === 'link' && link" :record="link" compact />

  <span
    v-else-if="column.cell === 'link' && value"
    class="truncate text-p-sm text-ink-gray-8"
  >
    {{ value }}
  </span>

  <!-- Right-aligned, because a column of numbers that does not line up is a
       column nobody can scan. -->
  <span
    v-else-if="numeric"
    class="w-full truncate text-right text-p-sm tabular-nums text-ink-gray-8"
  >
    {{ formatted }}
  </span>

  <span v-else class="truncate text-p-sm" :class="value ? 'text-ink-gray-8' : 'text-ink-gray-4'">
    {{ formatted }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Icon, Avatar, Rating } from '@/ui'
import RecordChip from './RecordChip.vue'
import { valueTheme } from '../../lib/fields'
import { dayjsLocal } from '@/ui'

const props = defineProps({
  column: { type: Object, required: true },
  value: { type: [String, Number, Boolean, Object, Array], default: null },
  states: { type: Array, default: () => [] },
  /** The row's resolved links, keyed by fieldname — see `_with_links`. */
  links: { type: Object, default: () => ({}) },
})

const link = computed(() => props.links?.[props.column.fieldname] || null)

const NUMERIC = ['number', 'currency', 'percent', 'duration']
const numeric = computed(() => NUMERIC.includes(props.column.cell))

const formatted = computed(() => {
  const raw = props.value
  if (raw === null || raw === undefined || raw === '') return '—'

  switch (props.column.cell) {
    case 'date':
      return dayjsLocal(raw).format('D MMM YYYY')
    case 'datetime':
      return dayjsLocal(raw).format('D MMM YYYY, HH:mm')
    case 'percent':
      return `${raw}%`
    case 'duration':
      return humanDuration(Number(raw) || 0)
    case 'html':
      // The list is not the place to render markup: a cell is one line, and
      // stripping is honest where interpreting would be a security decision.
      return (
        String(raw)
          .replace(/<[^>]*>/g, ' ')
          .replace(/\s+/g, ' ')
          .trim() || '—'
      )
    default:
      return String(raw)
  }
})

function humanDuration(seconds) {
  if (!seconds) return '—'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return (
    [days && `${days}d`, hours && `${hours}h`, minutes && `${minutes}m`]
      .filter(Boolean)
      .join(' ') || `${seconds}s`
  )
}
</script>

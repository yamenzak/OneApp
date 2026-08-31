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
  <RecordPreview
    v-else-if="column.cell === 'link' && link && spaceCode"
    :record="link"
    :fieldname="column.fieldname"
    :space-code="spaceCode"
    :screen="screen"
    :target="target"
  />

  <!-- Outside a screen — inside a preview card, say — there is nothing to
       bound a second lookup by, so the chip is the whole of it. -->
  <RecordChip v-else-if="column.cell === 'link' && link" :record="link" compact />

  <span v-else-if="column.cell === 'link' && value" class="truncate text-p-sm text-ink-gray-8">
    {{ value }}
  </span>

  <!-- Right-aligned, because a column of numbers that does not line up is a
       column nobody can scan. -->
  <span
    v-else-if="numeric"
    class="w-full truncate text-right text-p-sm tabular-nums"
    :class="[emphasis, value ? 'text-ink-gray-8' : 'text-ink-gray-4']"
  >
    {{ formatted }}
  </span>

  <span
    v-else
    class="truncate text-p-sm"
    :class="[emphasis, value ? 'text-ink-gray-8' : 'text-ink-gray-4']"
  >
    {{ formatted }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Icon, Avatar, Rating } from '@/ui'
import RecordChip from './RecordChip.vue'
import RecordPreview from './RecordPreview.vue'
import { valueTheme } from '../../lib/fields'
import { formatNumber, plainText } from '../../lib/format'
import { session } from '../../lib/session'
import { dayjsLocal } from '@/ui'

const props = defineProps({
  column: { type: Object, required: true },
  value: { type: [String, Number, Boolean, Object, Array], default: null },
  states: { type: Array, default: () => [] },
  /** The row's resolved links, keyed by fieldname — see `_with_links`. */
  links: { type: Object, default: () => ({}) },
  /**
   * The whole row. Read only by a Dynamic Link, whose target doctype lives in
   * another of its fields — every other cell needs `value` and nothing else,
   * which is why this is optional rather than the primary input.
   */
  row: { type: Object, default: () => ({}) },
  /** What bounds a link's preview lookup. Absent inside a preview card. */
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// The doctype's own emphasis. `bold` on a DocField is Frappe saying this is
// the field somebody scans the column for, and it costs one class to honour.
const emphasis = computed(() => (props.column.bold ? 'font-medium' : ''))

const link = computed(() => props.links?.[props.column.fieldname] || null)

// A Dynamic Link's target is on the row, not on the column — it is whatever
// the field named by `depends_on_field` holds — so the cell has to read it out
// of the record before anything downstream can look the value up.
const target = computed(() => {
  const column = props.column
  if (column.fieldtype !== 'Dynamic Link' || !column.depends_on_field) return ''
  return props.row?.[column.depends_on_field] || ''
})

// How this site renders a number when the field does not say. Read here rather
// than inside the formatter, which stays a pure question about a number and a
// docfield.
const formats = computed(() => session.data?.formats || {})

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
      return `${formatNumber(raw, props.column, formats.value)}%`
    case 'number':
    case 'currency':
      return formatNumber(raw, props.column, formats.value)
    case 'duration':
      return humanDuration(Number(raw) || 0, props.column)
    case 'html':
      // The list is not the place to render markup: a cell is one line, and
      // stripping is honest where interpreting would be a security decision.
      return plainText(raw) || '—'
    default:
      return String(raw)
  }
})

// Frappe's own two flags decide which parts of a duration are worth reading:
// `hide_days` folds days into hours, `hide_seconds` drops the tail. A field
// that sets neither reads the way it always did.
function humanDuration(seconds, column) {
  if (!seconds) return '—'
  const days = column.hide_days ? 0 : Math.floor(seconds / 86400)
  const hours = Math.floor((seconds - days * 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return (
    [
      days && `${days}d`,
      hours && `${hours}h`,
      minutes && `${minutes}m`,
      !column.hide_seconds && rest && `${rest}s`,
    ]
      .filter(Boolean)
      .join(' ') || (column.hide_seconds ? '0m' : `${seconds}s`)
  )
}
</script>

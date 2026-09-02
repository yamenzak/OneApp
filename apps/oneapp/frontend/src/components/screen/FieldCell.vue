<template>
  <!--
    One list cell. How a field reads in a list is a different question from how
    it is edited: a Check is a Switch in a form and a tick here, a Select is a
    dropdown there and a coloured badge here.

    The colour comes from the doctype's own `states` where it declares them, and
    from Frappe's word lists otherwise — so a status is not one colour in
    OneSpace and another in the desk.
  -->
  <!--
    A badge carries a colour and a glyph, both from the same place: the
    doctype's own `states` where it declares them, Frappe's word lists
    otherwise. So a status is not one colour in OneSpace and another in the
    desk, and it is not iconless in one list and iconed in the next.

    `prefix` rather than the label, because the glyph is the value said again
    rather than something extra to read — it should sit inside the badge, not
    beside it.
  -->
  <StateBadge v-if="column.cell === 'badge' && value" :label="value" :states="states" />

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

  <!--
    Tags. Badges rather than text, because a tag is a thing you scan a column
    for rather than read — and grey, all of them, because a tag is the
    workspace's own word and colouring it would be inventing a meaning the
    person who typed it did not give it.

    The overflow is counted rather than wrapped: a row is one line high, and a
    record with nine tags would otherwise push every other row's baseline down.
  -->
  <div v-else-if="column.cell === 'tags'" class="flex min-w-0 items-center gap-1">
    <Badge
      v-for="tag in shownTags"
      :key="tag"
      :label="tag"
      theme="gray"
      variant="subtle"
    />
    <Tooltip v-if="moreTags.length" :text="moreTags.join(', ')">
      <span class="shrink-0 text-p-xs text-ink-gray-5">+{{ moreTags.length }}</span>
    </Tooltip>
  </div>

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
import { Badge, Icon, Avatar, Rating, Tooltip } from '@/ui'
import StateBadge from './StateBadge.vue'
import RecordChip from './RecordChip.vue'
import RecordPreview from './RecordPreview.vue'
import { cellText, tagList } from '../../lib/cells'
import { plainText } from '../../lib/format'
import { session } from '../../lib/session'

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

// How many tags fit on one line of a list cell before the rest become a count.
// Three is what a 200px column holds at the sizes this list uses; past that the
// row either wraps — which pushes every other row's baseline down — or clips
// mid-word, and a count is more honest than either.
const TAGS_SHOWN = 3

const tags = computed(() =>
  props.column.cell === 'tags' ? tagList(props.value) : [],
)
const shownTags = computed(() => tags.value.slice(0, TAGS_SHOWN))
const moreTags = computed(() => tags.value.slice(TAGS_SHOWN))

const NUMERIC = ['number', 'currency', 'percent', 'duration']
const numeric = computed(() => NUMERIC.includes(props.column.cell))

// What the value says, from the one place that answers that — a gallery card
// draws the same values as pills over a photograph and must not have a second
// opinion about what a Duration looks like. See `lib/cells.js`.
const formatted = computed(() =>
  cellText(props.column, props.value, formats.value, link.value),
)
</script>

<template>
  <!--
    One list cell. How a field reads in a list is a different question from how
    it is edited: a Check is a Switch in a form and a tick here, a Select a
    dropdown there and a coloured badge here.
  -->
  <!--
    A badge carries a colour and a glyph, both from the doctype's own `states`
    where it declares them and Frappe's word lists otherwise — so a status is
    not one colour in OneSpace and another in the desk.

    `prefix` rather than the label, because the glyph is the value said again
    rather than something extra to read.
  -->
  <StateBadge v-if="column.cell === 'badge' && value" :label="value" :states="states" />

  <span v-else-if="column.cell === 'check'" class="text-ink-secondary">
    <Icon
      :name="value ? 'lucide-check' : 'lucide-minus'"
      :class="value ? 'size-4 text-ink-green-3' : 'size-4 text-ink-gray-4'"
    />
  </span>

  <Rating v-else-if="column.cell === 'rating'" :model-value="Number(value) || 0" disabled />

  <div v-else-if="column.cell === 'image'" class="flex items-center">
    <Avatar v-if="value" :image="value" :label="String(value)" shape="square" size="sm" />
    <!-- The lightest ink there is. An empty cell is the absence of a value and
         should read as one: at `ink-gray-4` a screen whose optional columns are
         mostly blank is a grid of dashes competing with the values beside
         them. -->
    <span v-else class="text-p-sm text-ink-gray-3">—</span>
  </div>

  <div v-else-if="column.cell === 'color'" class="flex items-center gap-2">
    <span
      v-if="value"
      class="size-3 shrink-0 rounded-full border border-outline-gray-2"
      :style="{ backgroundColor: value }"
    />
    <span
      class="truncate text-sm"
      :class="value ? 'text-ink-secondary' : 'text-ink-gray-3'"
    >{{ value || '—' }}</span>
  </div>

  <!--
    A link is a record. The server resolves the ids on a page to their title and
    image in one query per column, and falls back to the id when the target is
    one they may not read.
  -->
  <RecordPreview
    v-else-if="column.cell === 'link' && link && spaceCode"
    :record="link"
    :fieldname="column.fieldname"
    :space-code="spaceCode"
    :screen="screen"
    :target="target"
  />

  <!-- Outside a screen — inside a preview card, say — there is nothing to bound
       a second lookup by, so the chip is the whole of it. -->
  <RecordChip v-else-if="column.cell === 'link' && link" :record="link" compact />

  <span v-else-if="column.cell === 'link' && value" class="truncate text-sm text-ink-primary">
    {{ value }}
  </span>

  <!--
    Tags. Badges rather than text, because a tag is scanned for rather than
    read; grey, all of them, because colouring the workspace's own word would
    invent a meaning nobody gave it.

    The overflow is counted rather than wrapped: a row is one line high.
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
      <span class="shrink-0 text-p-xs text-ink-muted">+{{ moreTags.length }}</span>
    </Tooltip>
  </div>

  <!-- Right-aligned, because a column of numbers that does not line up is a
       column nobody can scan. -->
  <span
    v-else-if="numeric"
    class="w-full truncate text-end text-sm tabular-nums"
    :class="[emphasis, value ? 'text-ink-primary' : 'text-ink-gray-4']"
  >
    {{ formatted }}
  </span>

  <!-- `dir="auto"`: a cell of Arabic reads right to left beside a cell of
       English. Not on the numeric cell above — a number laid out from its own
       first character puts the currency symbol on the wrong side. -->
  <span
    v-else
    dir="auto"
    class="truncate text-sm"
    :class="[emphasis, value ? 'text-ink-primary' : 'text-ink-gray-4']"
  >
    {{ formatted }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Icon, Avatar, Rating, Tooltip } from '@/ui'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import RecordChip from '@/modules/onespace/components/screen/record/RecordChip.vue'
import RecordPreview from '@/modules/onespace/components/screen/bodies/RecordPreview.vue'
import { cellText, tagList } from '@/modules/onespace/lib/screen/cells'
import { session } from '@/modules/onespace/lib/shell/session'

const props = defineProps({
  column: { type: Object, required: true },
  value: { type: [String, Number, Boolean, Object, Array], default: null },
  states: { type: Array, default: () => [] },
  /** The row's resolved links, keyed by fieldname — see `_with_links`. */
  links: { type: Object, default: () => ({}) },
  /**
   * The whole row. Read only by a Dynamic Link, whose target doctype lives in
   * another of its fields — every other cell needs `value` and nothing else.
   */
  row: { type: Object, default: () => ({}) },
  /** What bounds a link's preview lookup. Absent inside a preview card. */
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// The doctype's own emphasis. `bold` on a DocField is Frappe saying this is the
// field somebody scans the column for.
const emphasis = computed(() => (props.column.bold ? 'font-medium' : ''))

const link = computed(() => props.links?.[props.column.fieldname] || null)

// A Dynamic Link's target is on the row, not on the column — whatever the field
// named by `depends_on_field` holds.
const target = computed(() => {
  const column = props.column
  if (column.fieldtype !== 'Dynamic Link' || !column.depends_on_field) return ''
  return props.row?.[column.depends_on_field] || ''
})

// How this site renders a number when the field does not say. Read here rather
// than inside the formatter, which stays a pure question.
const formats = computed(() => session.data?.formats || {})

// How many tags fit on one line before the rest become a count. Three is what a
// 200px column holds; past that the row wraps or clips mid-word.
const TAGS_SHOWN = 3

const tags = computed(() =>
  props.column.cell === 'tags' ? tagList(props.value) : [],
)
const shownTags = computed(() => tags.value.slice(0, TAGS_SHOWN))
const moreTags = computed(() => tags.value.slice(TAGS_SHOWN))

const NUMERIC = ['number', 'currency', 'percent', 'duration']
const numeric = computed(() => NUMERIC.includes(props.column.cell))

// What the value says, from the one place that answers that — a gallery card
// draws the same values as pills and must not have a second opinion about what
// a Duration looks like. See `lib/screen/cells.js`.
const formatted = computed(() =>
  cellText(props.column, props.value, formats.value, link.value),
)
</script>

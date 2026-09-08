<template>
  <!--
    The list: a screen's records, drawn as a table.

    The table itself is `RecordTable`, which the child grid inside a record also
    uses. What is left here is what makes this a *list*: which cell draws what,
    what a row click means, the favourites heart in the activity column's
    heading, and grouping runs of rows.
  -->
  <RecordTable
    v-model:selection="chosen"
    :columns="visible"
    :rows="rows"
    :row-height="52"
    :order-by="orderBy"
    :groups="groups"
    :fill="spec.title_field"
    :virtual-from="VIRTUAL_FROM"
    selectable
    band
    sticky
    fills
    extra-class="pb-1"
    :row-props="rowProps"
    @sort="emit('sort', $event)"
    @row-click="report || emit('open', $event)"
  >
    <!--
      How many, then favourites. The heart is last and the cell is end-aligned,
      so it lands on the x every row's heart lands on.

      The count goes in `#prefix` rather than the default slot because
      `ListHeaderCell` wraps its default in a `truncate` span, inside which
      `me-auto` does nothing — which is why this is a whole cell handed back.
    -->
    <template #header-__activity="{ pinned, style }">
      <ListHeaderCell class="justify-end" :class="pinned" :style="style">
        <template #prefix>
          <span class="whitespace-nowrap text-p-xs text-ink-gray-5">{{ counted }}</span>
        </template>
        <template #suffix>
          <Button
            icon="lucide-heart"
            :variant="favourites ? 'subtle' : 'ghost'"
            :theme="favourites ? 'red' : 'gray'"
            :label="__('Only my favourites')"
            :tooltip="__('Only my favourites')"
            @click="emit('favourites')"
          />
        </template>
      </ListHeaderCell>
    </template>

    <template #cell="{ column, row }">
      <TitleCell
        v-if="column.cell === 'title'"
        :row="row"
        :title-field="spec.title_field"
        :image-field="spec.image_field"
        @open="emit('open', row)"
      />
      <RowMeta
        v-else-if="column.cell === 'meta'"
        :meta="row._meta || {}"
        @like="emit('like', row)"
      />
      <!--
        Everything else is a value, and in a report a value you can type into.
        `EditableCell` decides whether this one may be — the server already said
        which fields are writable.
      -->
      <EditableCell
        v-else
        :column="column"
        :row="row"
        :spec="spec"
        :enabled="report"
        @change="emit('change', $event)"
      >
        <FieldCell
          :column="column.column"
          :value="row[column.key]"
          :row="row"
          :links="row._links || {}"
          :states="spec.states"
          :space-code="spec.space"
          :screen="spec.screen"
        />
      </EditableCell>
    </template>

    <!--
      The totals, where there are any. Only in a report: an extra aggregate query
      on every list anybody opens is a price the plain list should not pay.

      Under the money columns and nowhere else — `_summable` on the server
      decides which — and the word "Total" in the first column, so the row says
      what it is.
    -->
    <template v-if="report" #total="{ column }">
      <span
        v-if="column.key === first && hasTotals"
        class="text-p-sm font-medium text-ink-gray-7"
      >
        {{ __('Total') }}
      </span>
      <span
        v-else-if="totals[column.key] !== undefined"
        class="tabular-nums text-p-sm font-medium text-ink-gray-8"
      >
        {{ money(totals[column.key], column.column) }}
      </span>
    </template>
  </RecordTable>
</template>

<script setup>
import { computed } from 'vue'
import { Button, ListHeaderCell } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'
import RecordTable from '@/modules/onespace/components/screen/bodies/RecordTable.vue'
import EditableCell from '@/modules/onespace/components/screen/bodies/EditableCell.vue'
import FieldCell from '@/modules/onespace/components/screen/bodies/FieldCell.vue'
import TitleCell from '@/modules/onespace/components/screen/bodies/TitleCell.vue'
import RowMeta from '@/modules/onespace/components/screen/bodies/RowMeta.vue'
import { formatNumber } from '@/modules/onespace/lib/screen/format'
import { isNumericCell } from '@/modules/onespace/lib/screen/fields'
import { session } from '@/modules/onespace/lib/shell/session'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /** The columns the rows actually came back with, as the picker left them. */
  columns: { type: Array, default: () => [] },
  /** `field asc|desc`, so the header can show which way it is sorted. */
  orderBy: { type: String, default: '' },
  /** Whether the favourites filter is on, for the heart in the header. */
  favourites: { type: Boolean, default: false },
  /** How many rows there are, for the count in the activity header. */
  counted: { type: String, default: '' },
  /** Which column the rows are grouped under, or empty. */
  groupBy: { type: String, default: '' },
  /** The record open in the pane beside this list, if one is. */
  openRecord: { type: String, default: '' },
  /** What the money columns add up to over every row that matches, keyed by
   *  fieldname. Empty on a plain list, which does not ask for them. */
  totals: { type: Object, default: () => ({}) },
  /** The same sums per group. Empty unless the rows are grouped *and* this is
   *  a report — a subtotal is noise on a list. */
  groupTotals: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'like', 'sort', 'favourites', 'change'])

/**
 * A report rather than a list: cells you can type into, a row of totals, and a
 * row click that takes the cursor instead of opening the record. One body for
 * both, and the click is why they are separate view types.
 */
const report = computed(() => props.spec?.view_type === 'report')

const chosen = defineModel('selection', { type: Array, default: () => [] })

/**
 * The row the pane beside the list is showing.
 *
 * A record read against its list is the whole argument for the pane — mark
 * this one done, glance at the next, come back — and until now nothing said
 * which row you were reading. Scroll twenty rows and the pane belonged to
 * nobody.
 *
 * A tint rather than the selection's checkbox: ticking rows is a different
 * statement, and a person acting on four ticked rows while a fifth is open
 * must be able to tell the two apart at a glance.
 */
const rowProps = (row) => (row?.name && row.name === props.openRecord
  ? { class: 'bg-surface-gray-2', 'aria-current': 'true' }
  : {})

const META_FIELD = '__activity'

// How many rows before windowing them is worth the complexity it adds.
const VIRTUAL_FROM = 200

// One model for every column: the title field, activity and the values are all
// entries in the same list, so all three can be moved, resized, pinned and
// dropped in the picker.
//
// No screen-size branching, deliberately. A view is a saved answer to "what do
// I look at", and a phone that silently drops half of it is answering a
// different question — so the phone gets the same columns and scrolls.
const visible = computed(() => {
  const titleField = props.spec?.title_field
  return (props.columns || []).map((column) => ({
    key: column.fieldname,
    label: column.label,
    icon: column.icon,
    track: `${column.width}px`,
    width: column.width,
    pin: column.pin,
    sortable: column.fieldname !== META_FIELD,
    // Where the values sit: the reader's own answer where they gave one, and
    // otherwise the fieldtype's. The default lives here rather than on the
    // server because this is where the cell map that knows which fieldtypes are
    // numbers already is.
    align: column.align || (isNumericCell(column.cell) ? 'end' : ''),
    cell:
      column.fieldname === META_FIELD
        ? 'meta'
        : column.fieldname === titleField
          ? 'title'
          : column.cell,
    column,
  }))
})

// The first column, where the word "Total" goes: a band of numbers with nothing
// saying what they are is a mystery row.
const first = computed(() => visible.value[0]?.key || '')

const hasTotals = computed(() => Object.keys(props.totals || {}).length > 0)

// The site's own number settings, so a total reads the way the values above it
// do. `lib/screen/format.js` takes them as an argument rather than importing
// them, which is why they are read here.
const money = (value, column) =>
  formatNumber(value, column, session.data?.formats || {})

// Null when nothing is grouped, so the table can tell "no grouping" from "one
// group".
const groups = computed(() => {
  const field = props.groupBy
  if (!field) return null

  const made = []
  for (const row of props.rows) {
    const value = row[field]
    const label = value === null || value === undefined || value === '' ? '—' : String(value)
    const last = made[made.length - 1]
    if (last && last.label === label) last.rows.push(row)
    else made.push({ label, rows: [row], key: String(value ?? '') })
  }
  // What each group adds up to over every row that matches rather than over the
  // ones on this page — the only thing that makes a subtotal worth reading
  // under a footer saying "100 of 1,240".
  for (const group of made) group.note = subtotal(group.key)
  return made
})

/**
 * One group's sums, as the line beside its heading. Every summable column,
 * labelled: "Al-Ittihad · 412,500.00" beside "Halloway · 88,000.00" is two
 * numbers with nothing saying what they are the moment a second money column
 * appears.
 */
const subtotal = (key) => {
  if (!report.value) return ''
  const sums = props.groupTotals?.[key]
  if (!sums) return ''
  return visible.value
    .filter((column) => sums[column.key] !== undefined)
    .map((column) => `${column.label} ${money(sums[column.key], column.column)}`)
    .join(' · ')
}
</script>

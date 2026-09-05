<template>
  <!--
    The list: a screen's records, drawn as a table.

    One of several bodies a screen can be looked at through — the shell above
    owns everything a body does not: the breadcrumbs, the saved views, the
    filters, the selection bar and the footer.

    The table itself is `RecordTable`, which the child grid inside a record
    also uses. What is left here is what makes this a *list* rather than a
    table: which cell draws what, what a row click means, the favourites heart
    in the activity column's heading, and grouping runs of rows.
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
    @sort="emit('sort', $event)"
    @row-click="report || emit('open', $event)"
  >
    <!--
      How many, then favourites. The heart is last and the cell is end-aligned,
      so it lands on exactly the x every row's heart lands on — the header and
      the rows carry the same inset, so flush-right in both is the same pixel.
      Packed from the start it was not, which is what made the column of hearts
      look crooked.

      The count goes in `#prefix` rather than the default slot because
      `ListHeaderCell` wraps its default in a `truncate` span: `mr-auto` inside
      that does nothing, since the span is not the flex row. That is why this
      is a whole cell handed back rather than content handed in.
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
            label="Only my favourites"
            tooltip="Only my favourites"
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
        Everything else is a value, and in a report it is a value you can type
        into. `EditableCell` decides whether this particular one may be — the
        server already said which fields are writable — and draws the cell
        unchanged where it may not.
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
      The totals, where there are any. Only in a report: an extra aggregate
      query on every list anybody opens is a price the plain list should not
      pay, and Frappe puts its own totals behind a switch for the same reason.

      Under the money columns and nowhere else — `_summable` on the server
      decides which those are, and the word "Total" goes in the first column so
      the row says what it is rather than being a mystery number in a band.
    -->
    <template v-if="report" #total="{ column }">
      <span
        v-if="column.key === first && hasTotals"
        class="text-p-sm font-medium text-ink-gray-7"
      >
        Total
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
import RecordTable from './RecordTable.vue'
import EditableCell from './EditableCell.vue'
import FieldCell from './FieldCell.vue'
import TitleCell from './TitleCell.vue'
import RowMeta from './RowMeta.vue'
import { formatNumber } from '../../../lib/format'
import { isNumericCell } from '../../../lib/fields'
import { session } from '../../../lib/session'

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
  /**
   * What the money columns add up to over every row that matches, keyed by
   * fieldname. Empty on a plain list, which does not ask for them.
   */
  totals: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'like', 'sort', 'favourites', 'change'])

/**
 * A report rather than a list: cells you can type into, a row of totals, and a
 * row click that takes the cursor instead of opening the record.
 *
 * One body for both, because a report *is* the list plus those two things —
 * and the click is why they are separate view types rather than a switch. See
 * `lib/viewTypes.js`.
 */
const report = computed(() => props.spec?.view_type === 'report')

const chosen = defineModel('selection', { type: Array, default: () => [] })

const META_FIELD = '__activity'

// How many rows before windowing them is worth the complexity it adds.
const VIRTUAL_FROM = 200

// One model for every column. The title field renders with its avatar and id,
// activity renders its own cell, everything else is a value — but all three are
// entries in the same list, so all three can be moved, resized, pinned and
// dropped in the picker.
//
// No screen-size branching, deliberately. A view is a saved answer to "what do
// I look at", and a phone that silently drops half of it is answering a
// different question — so the phone gets the same columns and scrolls. Frappe
// CRM does the same, and it is only possible because the columns are the
// reader's to choose.
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
    // A number belongs against the right edge of its column, and a total
    // belongs under the numbers it adds up. `ChildTable` has done this since it
    // was written and said in a comment that the list did too; it did not.
    align: isNumericCell(column.cell) ? 'end' : '',
    cell:
      column.fieldname === META_FIELD
        ? 'meta'
        : column.fieldname === titleField
          ? 'title'
          : column.cell,
    column,
  }))
})

// The first column, which is where the word "Total" goes: a band of numbers
// with nothing saying what they are is a mystery row.
const first = computed(() => visible.value[0]?.key || '')

const hasTotals = computed(() => Object.keys(props.totals || {}).length > 0)

// The site's own number settings, so a total reads the way the values above it
// do — same separators, same decimals. `lib/format.js` takes them as an
// argument rather than importing them, which is why they are read here.
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
    else made.push({ label, rows: [row] })
  }
  return made
})
</script>

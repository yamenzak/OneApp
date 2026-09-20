<template>
  <!--
    A repeating group on a page a stranger opened — an order's lines, a claim's
    expenses, a schedule of rates. `docs/ONEFORMS.md` §15, stage 16.

    It is the one control here that is not a field: the reader adds and removes
    rows, so the thing being edited is a *list* and the page has to say how long
    it is and let them change that.

    **The same grid the record page draws**, through the same `RecordTable` that
    `ChildTable.vue` uses — the tracks, the sticky header, the scroller and the
    edges are all one component, so a supplier filling in five lines on a public
    form is looking at the table their buyer edits on the record. What this one
    leaves out is what a stranger has no use for: the column picker (the *form*
    chose the columns), the sheet, and the expand-a-row dialog, which needs a
    child doctype's own layout and is the reason a desk row with twenty fields
    is usable at all. A form asks for a handful.
  -->
  <div class="flex flex-col gap-2" :data-slot="`field-${field.fieldname}`">
    <div class="flex items-center justify-between gap-2">
      <span class="text-p-sm text-ink-secondary">
        {{ field.label }}<span v-if="field.reqd" class="text-ink-red-3"> *</span>
      </span>
      <div class="flex items-center gap-2">
        <!-- What is ticked, and the one thing worth doing to it — beside the
             count, the same as on the record. -->
        <Button
          v-if="chosen.length"
          size="sm"
          theme="red"
          variant="subtle"
          icon-left="lucide-trash-2"
          :label="__('Remove {0}', [chosen.length])"
          :data-slot="`drop-chosen-${field.fieldname}`"
          @click="removeChosen"
        />
        <span class="text-p-xs tabular-nums text-ink-muted">
          {{ rows.length === 1 ? __('{0} row', [rows.length]) : __('{0} rows', [rows.length]) }}
        </span>
      </div>
    </div>
    <p v-if="field.description" class="text-p-xs text-ink-muted">{{ field.description }}</p>

    <RecordTable
      v-if="rows.length"
      v-model:selection="chosen"
      :columns="tracks"
      :rows="rows"
      :row-key="rowKey"
      :row-height="44"
      selectable
      :row-props="rowProps"
      extra-class="rounded-6 border border-outline-gray-2"
    >
      <template #cell="{ column, row, index }">
        <!-- Frappe orders a child table by `idx`, so the number is the row's
             position and worth showing. It is also the handle. -->
        <span
          v-if="column.key === GUTTER"
          class="cursor-grab text-p-xs tabular-nums text-ink-muted"
          draggable="true"
          @dragstart="dragging = index"
          @dragend="endDrag"
        >{{ index + 1 }}</span>

        <div v-else-if="column.key === ACTIONS" class="flex w-full justify-end" @click.stop>
          <Button
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            :label="__('Take this row out')"
            :tooltip="__('Take it out')"
            :data-slot="`drop-${field.fieldname}`"
            @click="drop(index)"
          />
        </div>

        <!--
          A grid cell has no room for a label: the column header is the label,
          and repeating it in every row is the difference between a grid and a
          stack of forms. `FormControl` rather than the record's `FieldControl`,
          which wants a space and a screen and there is neither here.
        -->
        <!--
          `@click.stop` because a row in a selectable list toggles when it is
          clicked, and `RecordTable` lets a click on a control through rather
          than stopping it — so typing an answer also ticked the row, and the
          next press of Remove would have taken it out. Here rather than in
          `RecordTable`: on a record the tick is a bulk tool somebody reaches
          for deliberately, and changing it there is the record page's
          question, not this one's.
        -->
        <div
          v-else
          class="w-full"
          :data-slot="`cell-${field.fieldname}-${column.key}`"
          @click.stop
        >
          <FormControl
            :model-value="row[column.key]"
            :type="control(column.column.fieldtype)"
            :options="column.column.fieldtype === 'Select' ? choices(column.column) : undefined"
            class="w-full"
            @update:model-value="patch(index, column.key, $event)"
          />
        </div>
      </template>
    </RecordTable>

    <p v-else class="text-p-sm text-ink-muted">{{ __('Nothing here yet.') }}</p>

    <Button
      class="self-start"
      icon-left="lucide-plus"
      :label="__('Add row')"
      :disabled="rows.length >= (field.most || 100)"
      :data-slot="`add-${field.fieldname}`"
      @click="add"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, FormControl } from '@/ui'
import RecordTable from '@/modules/onespace/components/screen/bodies/RecordTable.vue'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  field: { type: Object, required: true },
  /** Which control a fieldtype gets — `PublicForm.vue` owns the map. */
  control: { type: Function, required: true },
})

const rows = defineModel({ type: Array, default: () => [] })

// The two columns that are not fields. Named rather than positional, because
// the cell slot dispatches on the key. Same names as `ChildTable.vue`.
const GUTTER = '__idx'
const ACTIONS = '__actions'

//: The narrowest a column is allowed to be, and the same number the record's
//: grid uses. Narrower than this and a four-column table is two columns and a
//: scrollbar; wider and it scrolls, which is what the scroller is for.
const NARROWEST = '6.5rem'

/** The columns, in the shape `RecordTable` takes. */
const tracks = [
  { key: GUTTER, label: '#', track: '2rem' },
  ...props.field.rows.map((column) => ({
    key: column.fieldname,
    label: column.label,
    track: `minmax(${NARROWEST}, 1fr)`,
    required: !!column.reqd,
    column,
  })),
  { key: ACTIONS, label: '', track: '3rem' },
]

// By position, not by key: none of these rows exists yet, so there is nothing
// else to key a selection on.
const rowKey = (_row, index) => index

/** A Select's own options, off the child column's `options`. */
const choices = (column) => String(column.options || '').split('\n').filter(Boolean)

/**
 * A new row, with every column present and empty.
 *
 * Present rather than absent: `v-model` on a key that does not exist yet makes
 * the row reactive only after the first keystroke, which loses that keystroke.
 */
const add = () => {
  rows.value = [
    ...rows.value,
    Object.fromEntries(props.field.rows.map((one) => [one.fieldname, ''])),
  ]
}

// Rows are replaced rather than mutated, so the page's own watch on the array
// sees the change.
const patch = (index, fieldname, value) => {
  rows.value = rows.value.map((one, at) => (at === index ? { ...one, [fieldname]: value } : one))
}

const drop = (at) => {
  rows.value = rows.value.filter((_one, index) => index !== at)
  chosen.value = []
}

// --- selection ---------------------------------------------------------------

const chosen = ref([])

const removeChosen = () => {
  // `Number`, because a row's identity is typed as a string in frappe-ui —
  // `new Set(['0']).has(0)` is false, which is how the record's grid once
  // ticked two rows and removed none.
  const going = new Set(chosen.value.map(Number))
  rows.value = rows.value.filter((_one, at) => !going.has(at))
  chosen.value = []
}

// --- reordering ---------------------------------------------------------------
//
// An order's lines have an order, and `idx` is it. Native drag and drop, the
// same as the record's grid.

const dragging = ref(null)
const draggedTo = ref(null)

const endDrag = () => {
  dragging.value = null
  draggedTo.value = null
}

// `data-row` and not `data-slot`, which is the one exception to the convention
// in this file and is not a preference: these land on `ListRowBase`'s root
// through `v-bind`, and that element already carries `data-slot="list-row"` —
// which is what frappe-ui's own structural CSS matches to make a row a grid.
// Setting `data-slot` here replaced it, and every row drew as a single column
// with its cells stacked. Cost one screenshot.
const rowProps = (_row, index) => ({
  'data-row': `${props.field.fieldname}-${index}`,
  class: draggedTo.value === index && dragging.value !== null ? 'bg-surface-gray-2' : '',
  onDragover: (event) => {
    event.preventDefault()
    draggedTo.value = index
  },
  onDrop: (event) => {
    event.preventDefault()
    const from = dragging.value
    endDrag()
    if (from === null || from === index) return
    const next = [...rows.value]
    const [moved] = next.splice(from, 1)
    next.splice(index, 0, moved)
    rows.value = next
    chosen.value = []
  },
})
</script>

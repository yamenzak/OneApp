<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="field.label" />
      <div class="flex items-center gap-2">
        <!--
          The sheet these rows are priced in. One control, because a table has
          one sheet: `sheets/feed.py` binds it and reopens it. Only on a saved
          record — a pull writes through the server.
        -->
        <OpenInSheet
          v-if="docname"
          :doctype="doctype"
          :docname="docname"
          :into="field.fieldname"
          :from="feed"
        />
        <!-- What is ticked, and the one thing worth doing to it. Beside the
             count rather than in a floating bar: a bar over the form to delete
             two lines of it is more chrome than the action deserves. -->
        <Button
          v-if="editable && chosen.length"
          size="sm"
          theme="red"
          variant="subtle"
          icon-left="lucide-trash-2"
          :label="__('Remove {0}', [chosen.length])"
          @click="removeChosen"
        />
        <!--
          Which of the child's fields are across, in what order, and how each
          one sits. The doctype's `in_list_view` is the default and only a
          guess: which four of fifteen matter depends on whether you are
          pricing the job or checking what was delivered.

          The list's own dialog, minus the three answers a child grid has no
          use for. It was a popover of checkboxes on the argument that only the
          list's columns carry an order — which was never true of the reader,
          only of what we had built.
        -->
        <!--
          Everything else this table can be told, in one place. Two of them and
          neither is daily: which fields go across, and pointing the rows at a
          sheet somebody made before the record existed.
        -->
        <Dropdown :options="tableMenu">
          <Button
            icon="lucide-settings-2"
            variant="ghost"
            size="sm"
            data-slot="child-columns"
            :label="__('Settings for these rows')"
            :tooltip="__('Settings for these rows')"
          />
        </Dropdown>
        <span class="text-p-xs tabular-nums text-ink-muted">
          {{ rows.length === 1 ? __('{0} row', [rows.length]) : __('{0} rows', [rows.length]) }}
        </span>
      </div>
    </div>

    <!-- Where these rows came from, when they came from a sheet. Under the
         label rather than beside it: it is a sentence, and a sentence in a row
         of controls pushes them onto a second line. -->
    <FeedNote
      v-if="feed"
      :feed="feed"
      :editable="editable"
      @changed="(one) => { feed = one }"
      @filled="filled"
    />

    <!--
      The same table the list is drawn with. `RecordTable` owns the tracks, the
      header, the scroller, the pinning and the edge; what is left here is what
      makes this a *grid* — a control in every cell, a row you can drag, a row
      you can open, and rows you can add and take away.
    -->
    <RecordTable
      v-if="rows.length"
      v-model:selection="chosen"
      :columns="tracks"
      :rows="shown"
      :row-key="rowKey"
      :row-height="44"
      :selectable="editable"
      :row-props="rowProps"
      :virtual-from="VIRTUAL_FROM"
      extra-class="rounded-6 border border-outline-gray-2"
    >
      <template #cell="{ column, row, index }">
        <!--
          Frappe orders a child table by `idx`, so the number is the row's
          position and worth showing. It is also the handle: the thing you drag
          to change the position is the thing that says what it is.
        -->
        <span
          v-if="column.key === GUTTER"
          class="text-p-xs tabular-nums text-ink-muted"
          :class="editable ? 'cursor-grab' : ''"
          :draggable="editable"
          @dragstart="dragging = index"
          @dragend="endDrag"
        >{{ index + 1 }}</span>

        <div v-else-if="column.key === ACTIONS" class="flex w-full items-center justify-end gap-0.5">
          <!-- The whole row, laid out the way the child doctype lays itself
               out: a child doctype with twenty fields is only usable this
               way. -->
          <Button
            icon="lucide-maximize-2"
            variant="ghost"
            :label="__('Open this row')"
            :tooltip="__('Open this row')"
            @click="open(index)"
          />
          <Button
            v-if="editable"
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            :label="__('Remove this row')"
            :tooltip="__('Remove this row')"
            @click="remove(index)"
          />
        </div>

        <!--
          `ruled` as well as `editable`: the doctype's own
          `read_only_depends_on` was honoured on the record form and not in
          this grid, so a field locked at a status could be typed into here
          and the save went through. `docs/UNIFICATION.md` §B5.
        -->
        <FieldControl
          v-else-if="writes(column.column, row)"
          :model-value="row[column.key]"
          :field="bare(column.column)"
          :space-code="spaceCode"
          :screen="screen"
          :doc="row"
          class="w-full"
          @update:model-value="patch(index, column.key, $event)"
        />
        <FieldCell
          v-else
          :column="column.column"
          :value="row[column.key]"
          :row="row"
        />
      </template>
    </RecordTable>

    <p v-else class="text-p-sm text-ink-muted">{{ __('Nothing here yet.') }}</p>

    <!--
      A page at a time, the way Frappe's own grid does it. Not about rendering
      cost — the table virtualises past two hundred rows — but about a form: a
      four-hundred-line invoice buries every other section on the record.
    -->
    <div v-if="rows.length > shown.length" class="flex items-center gap-2">
      <Button
        data-slot="child-more"
        :label="__('Show {0} more', [Math.min(PAGE, rows.length - shown.length)])"
        @click="showing += PAGE"
      />
      <Button
        variant="ghost"
        :label="__('Show all {0}', [rows.length])"
        @click="showing = rows.length"
      />
    </div>

    <Button
      v-if="editable"
      class="self-start"
      icon-left="lucide-plus"
      :label="__('Add row')"
      @click="add"
    />

    <!--
      One row, expanded. `RecordForm` and `FormSections` rather than a second
      layout engine, so a child row gets the child doctype's own tabs, section
      breaks, `depends_on` and every field property, with nothing written twice.
    -->
    <FillFromSheet
      v-if="docname"
      v-model="repointing"
      :doctype="doctype"
      :docname="docname"
      :into="field.fieldname"
      :fields="child.fields || []"
      :from="feed"
      @filled="filled"
    />

    <ColumnPicker
      v-model="picking"
      :chosen="chosenColumns"
      :offered="offered"
      :offers="GRID_OFFERS"
      @update:chosen="setColumns"
    />

    <Dialog v-model="expanded" :title="`${child.label} ${(editingAt ?? 0) + 1}`" size="3xl">
      <div v-if="editing" class="p-1">
        <RecordForm
          v-model:values="editing"
          :spec="childSpec"
          :space-code="spaceCode"
          :screen="screen"
          :disabled="!editable"
          :is-new="!editing.name"
        />
      </div>
      <template #actions>
        <Button variant="solid" :label="__('Done')" @click="expanded = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Button, Dialog, Dropdown, FormLabel } from '@/ui'
import RecordTable from '@/modules/onespace/components/screen/bodies/RecordTable.vue'
import FieldCell from '@/modules/onespace/components/screen/bodies/FieldCell.vue'
import FieldControl from '@/modules/onespace/components/screen/fields/FieldControl.vue'
import RecordForm from '@/modules/onespace/components/screen/record/RecordForm.vue'
import FillFromSheet from '@/modules/onesheet/components/FillFromSheet.vue'
import OpenInSheet from '@/modules/onesheet/components/OpenInSheet.vue'
import FeedNote from '@/modules/onesheet/components/FeedNote.vue'
import ColumnPicker from '@/modules/onespace/components/screen/views/ColumnPicker.vue'
import { workspace } from '@/shared/lib/workspace'
import { isNumericCell } from '@/modules/onespace/lib/screen/fields'
import { STATE, fieldState } from '@/shared/lib/fields/state'
import { remember, remembered } from '@/modules/onespace/lib/screen/childColumns'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The parent's docfield, whose `child` carries the child doctype's shape. */
  field: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  /** The record these rows hang off, where it has been saved. */
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
})

const emit = defineEmits(['reload'])

/**
 * The standing feed for this table, when there is one. Fetched here rather than
 * handed down: the record surface has no reason to know about sheets, and a
 * table that was never filled from one should cost nothing.
 */
const feed = ref(null)
const locked = computed(() => feed.value?.status === 'Locked')

async function readFeed() {
  if (!props.docname) {
    feed.value = null
    return
  }
  try {
    const found = await workspace.sheetFeeds(props.doctype, props.docname)
    feed.value = (found || []).find((one) => one.into === props.field.fieldname) || null
  } catch {
    // A record whose feeds cannot be read still draws its rows. This line is
    // provenance, not content.
    feed.value = null
  }
}

function filled(done) {
  if (done?.feed) feed.value = done.feed
  emit('reload')
}

onMounted(readFeed)
watch(() => [props.doctype, props.docname, props.field.fieldname], readFeed)

/** The rows, as the record holds them. Assigned whole, as Frappe stores them. */
const rows = defineModel('rows', { type: Array, default: () => [] })

const child = computed(() => props.field.child || { columns: [], fields: [], form: [] })

/**
 * Which columns are across, and who decided. `null` while nobody has chosen,
 * which is not the same as "chose none": the doctype's own `in_list_view`
 * answer stands until somebody disagrees with it.
 */
const picking = ref(false)
const repointing = ref(false)
const picked = ref(null)

const offered = computed(() => child.value.fields || [])

//: What a column carries in a grid. No width and no pin — the tracks share
//: whatever the pane gives them — and no grouping, which is a question about a
//: list of records rather than about the lines of one quotation.
const GRID_OFFERS = ['align']

/**
 * The columns across, as the doctype shaped them, with the reader's order and
 * alignment over the top.
 */
const columns = computed(() => {
  const by = Object.fromEntries(offered.value.map((one) => [one.fieldname, one]))
  if (!picked.value) return child.value.columns || []
  return picked.value
    .filter((one) => by[one.fieldname])
    .map((one) => ({ ...by[one.fieldname], align: one.align || '' }))
})

/** The same list in the shape `ColumnPicker` reads and writes. */
const chosenColumns = computed(() =>
  columns.value.map((one) => ({ fieldname: one.fieldname, align: one.align || '' })),
)

/**
 * What the gear offers. Columns always; the sheet only where these rows can
 * still be replaced — after a lock the document is the record, and offering to
 * repoint it would be offering something that is then refused.
 */
const tableMenu = computed(() => [
  {
    label: __('Which columns…'),
    icon: 'lucide-settings-2',
    onClick: () => { picking.value = true },
  },
  // Only once somebody has disagreed with the shipped set: "reset" against a table
  // nobody has changed is an offer to do nothing.
  ...(picked.value
    ? [{
      label: __('Reset the columns'),
      icon: 'lucide-rotate-ccw',
      onClick: () => resetColumns(),
    }]
    : []),
  ...(editable.value && props.docname && !locked.value
    ? [{
      label: __('Use a different sheet…'),
      icon: 'lucide-table-2',
      onClick: () => { repointing.value = true },
    }]
    : []),
])

const resetColumns = () => setColumns(null)

const setColumns = (next) => {
  // Every column off is not a table, it is a list of row numbers. Refused by
  // putting the doctype's answer back, which is what Reset does — and the
  // dialog already refuses to remove the last one.
  picked.value = next && next.length ? next : null
  remember(child.value.doctype, props.field.fieldname, picked.value)
}


const readColumns = () => {
  picked.value = remembered(child.value.doctype, props.field.fieldname)
}

onMounted(readColumns)
watch(() => [child.value.doctype, props.field.fieldname], readColumns)
const editable = computed(() => !props.disabled && !!child.value.editable && !!props.field.editable)

/**
 * Whether this cell may be typed in — §B5.
 *
 * `lib/fields/state.js`, the same call the form and the inline cell make.
 * Asked per *row* and not per column, because that is what the doctype's rules
 * are about: a table of ten rows can have three of them closed and seven open,
 * and a column-level answer would lock all ten or none.
 *
 * A cell that is not writable already draws `FieldCell` rather than a greyed
 * control, which is what the form has only just learned to do.
 */
const writes = (column, row) => fieldState(column, row || {}, {
  canWrite: editable.value,
}) === STATE.WRITABLE

// `RecordForm` reads `form` for the layout and `all_columns` for the fields.
// Shaped here rather than on the server so the payload stays one description of
// a child table rather than one shaped for each consumer.
const childSpec = computed(() => ({
  doctype: child.value.doctype,
  form: child.value.form,
  all_columns: child.value.fields,
  screen: `${props.screen}:${props.field.fieldname}`,
}))

/**
 * A grid cell has no room for a label or a description: the column header is
 * the label, and repeating it inside every control in every row is the
 * difference between a grid and a stack of forms. The behaviour still travels.
 */
const bare = (column) => ({ ...column, label: '', icon: null, description: null })

// The two columns that are not fields. Named rather than positional, because
// the cell slot dispatches on the key.
const GUTTER = '__idx'
const ACTIONS = '__actions'

// A child doctype with four hundred lines is an invoice, not a mistake.
const VIRTUAL_FROM = 200

// How many rows are across before somebody asks for more. Frappe's own grid
// pages at fifty: more than any real document has, less than a section that
// buries the rest of the form.
const PAGE = 50

const showing = ref(PAGE)
const shown = computed(() => rows.value.slice(0, showing.value))

// Back to one page whenever the table is for something else. Somebody who
// expanded four hundred lines on the last invoice did not ask for four hundred
// on this one.
watch(() => [props.docname, props.field.fieldname], () => { showing.value = PAGE })

// A row added past the fold has to be visible, or Add row appears to do
// nothing. One row: filling three hundred from a sheet is not a reason to draw
// three hundred.
watch(() => rows.value.length, (many, was) => {
  if (many === was + 1 && many > showing.value) showing.value = many
})

//: The narrowest a child column is allowed to be. A grid lives inside a record
//: pane, which is about 460px, and at the 8rem this used to be a five-column
//: table was 1250px wide — two columns visible and the other three, headers
//: included, scrolled off the right. 5rem fits four, which is what the pane is
//: for; anything wider still scrolls, which is what the scroller is for.
const NARROWEST = '6.5rem'

/**
 * The columns, in the shape `RecordTable` takes: a narrow one for the row
 * number, a wide one for the actions, the rest shared.
 *
 * No `width`, and so no pinning and no fill — those are arithmetic over pixels,
 * and these tracks share whatever they are given.
 */
const tracks = computed(() => [
  { key: GUTTER, label: '#', track: '2rem' },
  ...columns.value.map((column) => ({
    key: column.fieldname,
    label: column.label,
    track: `minmax(${NARROWEST}, 1fr)`,
    required: !!column.reqd,
    // A number belongs against the right edge of its column. Which cells are
    // numbers is generated from the same fieldtype map that decides how a value
    // is drawn, so this and the list cannot disagree.
    align: column.align || (isNumericCell(column.cell) ? 'end' : ''),
    column,
  })),
  { key: ACTIONS, label: '', track: '5rem' },
])

// By position, not by key: a saved child row has a `name` and a new one does
// not, so half the rows in an edited table have nothing to key a selection on.
const rowKey = (_row, index) => index

// The drag handlers, bound onto each row. The table owns the row element; what
// a row *does* is still ours.
const rowProps = (_row, index) => ({
  class: draggedTo.value === index && dragging.value !== null ? 'bg-surface-gray-2' : '',
  onDragover: (event) => {
    event.preventDefault()
    draggedTo.value = index
  },
  onDrop: (event) => {
    event.preventDefault()
    drop(index)
  },
})

const expanded = ref(false)
const editingAt = ref(null)
const editing = computed({
  get: () => (editingAt.value === null ? null : rows.value[editingAt.value]),
  set: (value) => {
    if (editingAt.value !== null) replace(editingAt.value, value)
  },
})

const open = (index) => {
  editingAt.value = index
  expanded.value = true
}

// Rows are replaced rather than mutated: the array is the record's, and the
// record's own dirty tracking watches the reference.
const replace = (index, row) => {
  rows.value = rows.value.map((one, at) => (at === index ? row : one))
}

const patch = (index, fieldname, value) => {
  replace(index, { ...rows.value[index], [fieldname]: value })
}

// No `name`, which is how Frappe tells a new row from an edited one. `idx` is
// its position, and the server renumbers on save.
const add = () => {
  rows.value = [...rows.value, { idx: rows.value.length + 1 }]
}

const remove = (index) => {
  rows.value = rows.value.filter((_row, at) => at !== index)
  if (editingAt.value === index) expanded.value = false
  chosen.value = []
}

// --- selection ---------------------------------------------------------------
//
// frappe-ui's own, keyed by position through `rowKey`. Every operation that
// moves a row clears it: a selection held by position through a reorder is a
// selection of different rows, which is the kind of bug that deletes the wrong
// line.

const chosen = ref([])

const removeChosen = () => {
  // `Number`, because a row's identity is typed as a string in frappe-ui —
  // `new Set(['0']).has(0)` is false, and the first version ticked two rows and
  // removed none.
  const going = new Set(chosen.value.map(Number))
  rows.value = rows.value.filter((_row, at) => !going.has(at))
  if (editingAt.value !== null && going.has(editingAt.value)) expanded.value = false
  chosen.value = []
}

// --- reordering ---------------------------------------------------------------
//
// Native drag and drop, and `idx` rewritten to match: the record in the browser
// is what the form reads back, so leaving the old numbers would show the rows
// in one order and save them in another.

const dragging = ref(null)
const draggedTo = ref(null)

const endDrag = () => {
  dragging.value = null
  draggedTo.value = null
}

const drop = (index) => {
  const from = dragging.value
  endDrag()
  if (from === null || from === index) return

  const next = [...rows.value]
  const [moved] = next.splice(from, 1)
  next.splice(index, 0, moved)
  rows.value = next.map((row, at) => ({ ...row, idx: at + 1 }))
  chosen.value = []
  // The expanded row followed its position rather than its contents, which is
  // the wrong half of the pair.
  expanded.value = false
}
</script>

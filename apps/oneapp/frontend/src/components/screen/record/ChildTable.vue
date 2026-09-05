<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="field.label" />
      <div class="flex items-center gap-2">
        <!--
          Read these rows off a spreadsheet. Here rather than in the record's
          action menu because this is where somebody with a priced estimate in
          front of them is already looking — and because what it replaces is
          exactly these rows and nothing else on the document.

          Only on a saved record: a pull writes through the server, and there
          is nothing to write to until the document exists.
        -->
        <FillFromSheet
          v-if="editable && docname && !locked"
          :doctype="doctype"
          :docname="docname"
          :into="field.fieldname"
          :fields="child.fields || []"
          :from="feed"
          @filled="filled"
        />
        <!-- What is ticked, and the one thing worth doing to it. Beside the
             count rather than in a floating bar: a child table is a few rows
             inside a form, and a bar over the form to delete two lines of it
             is more chrome than the action deserves. -->
        <Button
          v-if="editable && chosen.length"
          size="sm"
          theme="red"
          variant="subtle"
          icon-left="lucide-trash-2"
          :label="`Remove ${chosen.length}`"
          @click="removeChosen"
        />
        <!--
          Which of the child's fields are across. The doctype's `in_list_view`
          is the default and it is only a guess: an invoice line has fifteen
          fields, four fit across a form column, and which four matter depends
          on whether you are pricing the job or checking what was delivered.

          A gear rather than a dialog. The list's picker is a dialog because a
          column there also carries an order, a width, an edge and a pin; here
          a column carries nothing but whether it is on.
        -->
        <Popover v-model:open="picking">
          <template #trigger>
            <Button
              icon="lucide-settings-2"
              variant="ghost"
              size="sm"
              data-slot="child-columns"
              label="Which columns"
              tooltip="Which columns"
            />
          </template>
          <template #default>
            <div class="flex w-64 flex-col gap-2 p-2">
              <div class="flex items-baseline justify-between">
                <span class="text-p-sm font-medium text-ink-gray-8">Columns</span>
                <Button
                  v-if="picked"
                  variant="ghost"
                  size="sm"
                  label="Reset"
                  @click="resetColumns"
                />
              </div>
              <FadedScroll class="max-h-72">
                <div class="flex flex-col gap-1.5 pe-1">
                  <Checkbox
                    v-for="one in offered"
                    :key="one.fieldname"
                    :model-value="shows(one.fieldname)"
                    :label="one.label || one.fieldname"
                    @update:model-value="toggleColumn(one.fieldname, $event)"
                  />
                </div>
              </FadedScroll>
            </div>
          </template>
        </Popover>
        <span class="text-p-xs tabular-nums text-ink-gray-5">
          {{ rows.length }} {{ rows.length === 1 ? 'row' : 'rows' }}
        </span>
      </div>
    </div>

    <!-- Where these rows came from, when they came from a sheet. Under the
         label rather than beside it: it is a sentence, and a sentence in a row
         of controls is the thing that pushes them onto a second line. -->
    <FeedNote
      v-if="feed"
      :feed="feed"
      :editable="editable"
      @changed="(one) => { feed = one }"
    />

    <!--
      The same table the list is drawn with.

      `RecordTable` owns the tracks, the header, the scroller, the pinning and
      the edge that says there is more; what is left here is what makes this a
      *grid* rather than a list — a control in every cell, a row you can drag,
      a row you can open, and rows you can add and take away.

      It used to own none of that and rebuild the little it had, which is how
      the grid ended up with no widths, no sticky header, and a header inset
      twelve pixels from the rows underneath it.
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
          position and worth showing: it is what a person means when they say
          "the third line". It is also the handle — the number *is* the
          position, so the thing you drag to change it is the thing that says
          what it is, rather than a second grip column beside it.
        -->
        <span
          v-if="column.key === GUTTER"
          class="text-p-xs tabular-nums text-ink-gray-5"
          :class="editable ? 'cursor-grab' : ''"
          :draggable="editable"
          @dragstart="dragging = index"
          @dragend="endDrag"
        >{{ index + 1 }}</span>

        <div v-else-if="column.key === ACTIONS" class="flex w-full items-center justify-end gap-0.5">
          <!-- The whole row, laid out the way the child doctype lays itself
               out. A handful of columns fit across; a child doctype with
               twenty fields is only usable this way. -->
          <Button
            icon="lucide-maximize-2"
            variant="ghost"
            label="Open this row"
            tooltip="Open this row"
            @click="open(index)"
          />
          <Button
            v-if="editable"
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            label="Remove this row"
            tooltip="Remove this row"
            @click="remove(index)"
          />
        </div>

        <FieldControl
          v-else-if="editable && column.column.editable"
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

    <p v-else class="text-p-sm text-ink-gray-5">Nothing here yet.</p>

    <!--
      A page at a time, the way Frappe's own grid does it. The table
      virtualises past two hundred rows, so this is not about rendering cost —
      it is about a form. A four-hundred-line invoice with every line drawn is
      a section that buries every other section on the record, and the person
      who opened it wanted the total.
    -->
    <div v-if="rows.length > shown.length" class="flex items-center gap-2">
      <Button
        data-slot="child-more"
        :label="`Show ${Math.min(PAGE, rows.length - shown.length)} more`"
        @click="showing += PAGE"
      />
      <Button
        variant="ghost"
        :label="`Show all ${rows.length}`"
        @click="showing = rows.length"
      />
    </div>

    <Button
      v-if="editable"
      class="self-start"
      icon-left="lucide-plus"
      label="Add row"
      @click="add"
    />

    <!--
      One row, expanded. `RecordForm` and `FormSections` rather than a second
      layout engine — so a child row gets the child doctype's own tabs, section
      and column breaks, `depends_on`, and every field property the parent's
      form honours, with nothing written twice.

      A drawer on desktop and a sheet on a phone would be the ideal split; a
      Dialog is both, and is what the create form already uses.
    -->
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
        <Button variant="solid" label="Done" @click="expanded = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { Button, Checkbox, Dialog, FormLabel, Popover } from '@/ui'
import FadedScroll from '../../FadedScroll.vue'
import RecordTable from '../bodies/RecordTable.vue'
import FieldCell from '../bodies/FieldCell.vue'
import FieldControl from '../fields/FieldControl.vue'
import RecordForm from './RecordForm.vue'
import FillFromSheet from '../../sheets/FillFromSheet.vue'
import FeedNote from '../../sheets/FeedNote.vue'
import { workspace } from '../../../lib/workspace'
import { isNumericCell } from '../../../lib/fields'
import { remember, remembered } from '../../../lib/childColumns'

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
 * The standing feed for this table, when there is one.
 *
 * Fetched here rather than handed down, because the record surface has no
 * reason to know about sheets and a table that was never filled from one
 * should cost nothing — which is what `docname` being empty on a new record
 * makes true.
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
 * Which columns are across, and who decided.
 *
 * `null` while nobody has chosen, which is not the same as "chose none": the
 * doctype's own `in_list_view` answer stands until somebody disagrees with it,
 * and a table nobody has touched should follow a doctype that changes its mind.
 */
const picking = ref(false)
const picked = ref(null)

const offered = computed(() => child.value.fields || [])

const columns = computed(() => {
  if (!picked.value) return child.value.columns || []
  const by = Object.fromEntries(offered.value.map((one) => [one.fieldname, one]))
  // In the child doctype's own field order rather than the order they were
  // ticked in: a grid is read left to right and the author of the doctype
  // already decided what that order is.
  return offered.value.filter((one) => picked.value.includes(one.fieldname)).map(
    (one) => by[one.fieldname],
  )
})

const shows = (fieldname) =>
  picked.value
    ? picked.value.includes(fieldname)
    : (child.value.columns || []).some((one) => one.fieldname === fieldname)

const toggleColumn = (fieldname, on) => {
  const now = offered.value
    .map((one) => one.fieldname)
    .filter((name) => (name === fieldname ? on : shows(name)))
  // Every column off is not a table, it is a list of row numbers. Refused by
  // putting the doctype's answer back, which is also what Reset does.
  picked.value = now.length ? now : null
  remember(child.value.doctype, props.field.fieldname, picked.value)
}

const resetColumns = () => {
  picked.value = null
  remember(child.value.doctype, props.field.fieldname, null)
}

const readColumns = () => {
  picked.value = remembered(child.value.doctype, props.field.fieldname)
}

onMounted(readColumns)
watch(() => [child.value.doctype, props.field.fieldname], readColumns)
const editable = computed(() => !props.disabled && !!child.value.editable && !!props.field.editable)

// `RecordForm` reads `form` for the layout and `all_columns` for the fields —
// the same two things the child resolver produced, under the names the form
// already expects. Shaped here rather than on the server so the payload stays
// one description of a child table rather than one shaped for each consumer.
const childSpec = computed(() => ({
  doctype: child.value.doctype,
  form: child.value.form,
  all_columns: child.value.fields,
  screen: `${props.screen}:${props.field.fieldname}`,
}))

/**
 * A grid cell has no room for a label or a description.
 *
 * The column header is the label, and repeating it inside every control in
 * every row is the difference between a grid and a stack of forms. The
 * behaviour — required, read-only, the bounds — all still travels.
 */
const bare = (column) => ({ ...column, label: '', icon: null, description: null })

// The two columns that are not fields. Named rather than positional, because
// the cell slot dispatches on the key and `column.key === columns[0]` is a
// thing that breaks the moment a column is added in front of it.
const GUTTER = '__idx'
const ACTIONS = '__actions'

// A child doctype with four hundred lines is an invoice, not a mistake.
const VIRTUAL_FROM = 200

// How many rows are across before somebody asks for more. Frappe's own grid
// pages at fifty and it is the right number for the same reason: it is more
// than any real document has and less than a section that buries the rest of
// the form.
const PAGE = 50

const showing = ref(PAGE)
const shown = computed(() => rows.value.slice(0, showing.value))

// Back to one page whenever the table is for something else — a different
// record, or a different table on the same one. Somebody who expanded four
// hundred lines on the last invoice did not ask for four hundred on this one.
watch(() => [props.docname, props.field.fieldname], () => { showing.value = PAGE })

// A row added past the fold has to be visible, or Add row appears to do
// nothing. One row, deliberately: filling three hundred from a sheet is not a
// reason to draw three hundred.
watch(() => rows.value.length, (many, was) => {
  if (many === was + 1 && many > showing.value) showing.value = many
})

/**
 * The columns, in the shape `RecordTable` takes.
 *
 * A narrow one for the row number, a wide one for the actions, and the rest
 * shared — the doctype's own `columns` hint would be a nicer weighting, but a
 * child grid is already inside a form column and the honest answer at that
 * width is equal shares.
 *
 * No `width`, and so no pinning and no fill: those are arithmetic over pixels,
 * and these tracks share whatever they are given. The table does the right
 * thing with either.
 */
const tracks = computed(() => [
  { key: GUTTER, label: '#', track: '2rem' },
  ...columns.value.map((column) => ({
    key: column.fieldname,
    label: column.label,
    track: 'minmax(8rem, 1fr)',
    required: !!column.reqd,
    // A number belongs against the right edge of its column. Which cells are
    // numbers is generated from the same fieldtype map that decides how a
    // value is drawn, so this and the list cannot disagree about it.
    align: isNumericCell(column.cell) ? 'end' : '',
    column,
  })),
  { key: ACTIONS, label: '', track: '5rem' },
])

// By position, not by key.
//
// A saved child row has a `name` and a new one does not — that is how Frappe
// tells an update from an insert — so half the rows in an edited table have
// nothing to key a selection on. Position is what a child table already is:
// `idx` ordered, renumbered on save.
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
// frappe-ui's own now, keyed by position through `rowKey`. It draws the tick
// box, the select-all in the header, and the row inset that goes with them —
// all of which this used to hand-roll in a column of its own, and the inset it
// got wrong.
//
// Every operation that moves a row still clears it. A selection held by
// position through a reorder is a selection of different rows, and that is the
// kind of bug that deletes the wrong line.

const chosen = ref([])

const removeChosen = () => {
  // `Number`, because the selection comes back as frappe-ui stored it and a
  // row's identity is typed as a string there — `new Set(['0']).has(0)` is
  // false, and the first version of this ticked two rows and removed none.
  const going = new Set(chosen.value.map(Number))
  rows.value = rows.value.filter((_row, at) => !going.has(at))
  if (editingAt.value !== null && going.has(editingAt.value)) expanded.value = false
  chosen.value = []
}

// --- reordering ---------------------------------------------------------------
//
// Native drag and drop, and `idx` rewritten to match: Frappe orders a child
// table by that column and renumbers on save, but the record in the browser is
// what the form reads back, so leaving the old numbers there would show the
// rows in one order and save them in another.

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
  // the wrong half of the pair. Closing is the honest answer to "the thing you
  // had open is somewhere else now".
  expanded.value = false
}
</script>

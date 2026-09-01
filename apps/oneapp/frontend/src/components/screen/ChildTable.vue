<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="field.label" />
      <div class="flex items-center gap-2">
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
        <span class="text-p-xs tabular-nums text-ink-gray-5">
          {{ rows.length }} {{ rows.length === 1 ? 'row' : 'rows' }}
        </span>
      </div>
    </div>

    <!--
      A grid, not the list.

      `ListBody` carries virtualization, grouping, saved views, favourites, a
      selection bar and a row click that navigates to a record route — none of
      which a child table wants, and several of which would be actively wrong
      inside a form. What is genuinely shared is the cell dispatch, and that is
      `FieldControl` and `FieldCell`, which both are used here.
    -->
    <!--
      A child grid is wider than the pane it sits in more often than not — five
      columns at their minimum is eight hundred pixels — so it scrolls, and it
      says which side there is more on. Silently clipping three columns is how
      a required field nobody could see failed a save.
    -->
    <FadedScroll
      v-if="rows.length"
      axis="x"
      class="rounded-6 border border-outline-gray-2"
    >
      <!--
        `px-3` on the List rather than `list-row-px-3`.

        That class sets frappe-ui's public `--list-row-padding-x`, which the
        header reads — but the rows read a private one that the library only
        sets on rows marked `[data-interactive]`, and a child row has no click
        handler so it is not one. The result was a header inset twelve pixels
        and rows flush against the border under it, every column out of true
        with its own heading. Padding the grid itself moves both together.
      -->
      <List :columns="tracks" :row-height="44" class="w-max min-w-full px-3">
        <ListHeader>
          <ListHeaderCell>
            <div class="flex items-center gap-2">
              <Checkbox
                v-if="editable"
                :model-value="allChosen"
                :indeterminate="!!chosen.length && !allChosen"
                aria-label="Select every row"
                @update:model-value="chooseAll"
              />
              <span>#</span>
            </div>
          </ListHeaderCell>
          <ListHeaderCell
            v-for="column in columns"
            :key="column.fieldname"
            :class="isNumericCell(column.cell) ? 'justify-end' : ''"
          >
            {{ column.label }}
            <!-- The child doctype's own `reqd`, said where the label is said.
                 A grid cell has no room for a label, so without this the only
                 warning that a column may not be left blank is the save
                 failing. -->
            <span v-if="column.reqd" class="text-ink-red-4" aria-hidden="true">*</span>
          </ListHeaderCell>
          <ListHeaderCell />
        </ListHeader>

        <ListRows :items="rows" row-key="name" v-slot="{ item: row, value, index }">
          <ListRow
            :value="value"
            :class="draggedTo === index && dragging !== null ? 'bg-surface-gray-2' : ''"
            @dragover.prevent="draggedTo = index"
            @drop.prevent="drop(index)"
          >
            <!-- Frappe orders a child table by `idx`, so the number is the
                 row's position and worth showing: it is what a person means
                 when they say "the third line". It is also the handle — the
                 number *is* the position, so the thing you drag to change it
                 is the thing that says what it is, rather than a second grip
                 column beside it. -->
            <ListCell>
              <div class="flex w-full items-center gap-2">
                <Checkbox
                  v-if="editable"
                  :model-value="chosen.includes(index)"
                  :aria-label="`Select row ${index + 1}`"
                  @update:model-value="choose(index, $event)"
                />
                <span
                  class="text-p-xs tabular-nums text-ink-gray-5"
                  :class="editable ? 'cursor-grab' : ''"
                  :draggable="editable"
                  @dragstart="dragging = index"
                  @dragend="endDrag"
                >{{ index + 1 }}</span>
              </div>
            </ListCell>
            <ListCell
              v-for="column in columns"
              :key="column.fieldname"
              :class="isNumericCell(column.cell) && !editable ? 'justify-end' : ''"
            >
              <FieldControl
                v-if="editable && column.editable"
                :model-value="row[column.fieldname]"
                :field="bare(column)"
                :space-code="spaceCode"
                :screen="screen"
                :doc="row"
                class="w-full"
                @update:model-value="patch(index, column.fieldname, $event)"
              />
              <FieldCell v-else :column="column" :value="row[column.fieldname]" :row="row" />
            </ListCell>
            <ListCell>
              <div class="flex w-full items-center justify-end gap-0.5">
                <!-- The whole row, laid out the way the child doctype lays
                     itself out. A handful of columns fit across; a child
                     doctype with twenty fields is only usable this way. -->
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
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </FadedScroll>

    <p v-else class="text-p-sm text-ink-gray-5">Nothing here yet.</p>

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
import { computed, ref } from 'vue'
import {
  Button,
  Checkbox,
  Dialog,
  FormLabel,
  List,
  ListHeader,
  ListHeaderCell,
  ListRows,
  ListRow,
  ListCell,
} from '@/ui'
import FadedScroll from './FadedScroll.vue'
import FieldCell from './FieldCell.vue'
import FieldControl from './FieldControl.vue'
import RecordForm from './RecordForm.vue'
import { isNumericCell } from '../../lib/fields'

const props = defineProps({
  /** The parent's docfield, whose `child` carries the child doctype's shape. */
  field: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})

/** The rows, as the record holds them. Assigned whole, as Frappe stores them. */
const rows = defineModel('rows', { type: Array, default: () => [] })

const child = computed(() => props.field.child || { columns: [], fields: [], form: [] })
const columns = computed(() => child.value.columns || [])
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

/**
 * Grid track sizes, in the shape `List` takes.
 *
 * A narrow one for the row number, a wide one for the actions, and the rest
 * shared — the doctype's own `columns` hint would be a nicer weighting, but a
 * child grid is already inside a form column and the honest answer at that
 * width is equal shares.
 */
const tracks = computed(() => [
  gutter.value,
  ...columns.value.map(() => 'minmax(8rem, 1fr)'),
  '5rem',
])

// The first track holds the row number, and the tick box as well when the grid
// is editable. 2rem fitted the number alone; with a checkbox beside it the two
// were on top of each other.
const gutter = computed(() => (editable.value ? '3.5rem' : '2rem'))

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
// By position, not by key. A saved child row has a `name` and a new one does
// not — that is how Frappe tells an update from an insert — so half the rows in
// an edited table have nothing to key a selection on. Position is what a child
// table already is: `idx` ordered, renumbered on save.
//
// Which is also why every operation that moves a row clears the selection. A
// selection held by position through a reorder is a selection of different
// rows, and that is the kind of bug that deletes the wrong line.

const chosen = ref([])

const allChosen = computed(
  () => rows.value.length > 0 && chosen.value.length === rows.value.length,
)

const choose = (index, ticked) => {
  chosen.value = ticked
    ? [...chosen.value, index]
    : chosen.value.filter((at) => at !== index)
}

const chooseAll = (ticked) => {
  chosen.value = ticked ? rows.value.map((_row, at) => at) : []
}

const removeChosen = () => {
  const going = new Set(chosen.value)
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

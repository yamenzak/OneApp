<template>
  <div class="flex flex-col gap-2">
    <div class="flex items-center justify-between gap-2">
      <FormLabel :label="field.label" />
      <span class="text-p-xs tabular-nums text-ink-gray-5">
        {{ rows.length }} {{ rows.length === 1 ? 'row' : 'rows' }}
      </span>
    </div>

    <!--
      A grid, not the list.

      `ListBody` carries virtualization, grouping, saved views, favourites, a
      selection bar and a row click that navigates to a record route — none of
      which a child table wants, and several of which would be actively wrong
      inside a form. What is genuinely shared is the cell dispatch, and that is
      `FieldControl` and `FieldCell`, which both are used here.
    -->
    <div v-if="rows.length" class="overflow-x-auto rounded-6 border border-outline-gray-2">
      <List :columns="tracks" :row-height="44" class="w-max min-w-full list-row-px-3">
        <ListHeader>
          <ListHeaderCell>#</ListHeaderCell>
          <ListHeaderCell v-for="column in columns" :key="column.fieldname">
            {{ column.label }}
          </ListHeaderCell>
          <ListHeaderCell />
        </ListHeader>

        <ListRows :items="rows" row-key="name" v-slot="{ item: row, value, index }">
          <ListRow :value="value">
            <!-- Frappe orders a child table by `idx`, so the number is the
                 row's position and worth showing: it is what a person means
                 when they say "the third line". -->
            <ListCell>
              <span class="text-p-xs tabular-nums text-ink-gray-5">{{ index + 1 }}</span>
            </ListCell>
            <ListCell v-for="column in columns" :key="column.fieldname">
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
    </div>

    <p v-else class="text-p-sm text-ink-gray-5">Nothing here yet.</p>

    <Button
      v-if="editable"
      class="self-start"
      icon-left="lucide-plus"
      :label="`Add a ${child.label.toLowerCase()}`"
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
  Dialog,
  FormLabel,
  List,
  ListHeader,
  ListHeaderCell,
  ListRows,
  ListRow,
  ListCell,
} from '@/ui'
import FieldCell from './FieldCell.vue'
import FieldControl from './FieldControl.vue'
import RecordForm from './RecordForm.vue'

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
const bare = (column) => ({ ...column, label: '', description: null })

/**
 * Grid track sizes, in the shape `List` takes.
 *
 * A narrow one for the row number, a wide one for the actions, and the rest
 * shared — the doctype's own `columns` hint would be a nicer weighting, but a
 * child grid is already inside a form column and the honest answer at that
 * width is equal shares.
 */
const tracks = computed(() => ['2rem', ...columns.value.map(() => 'minmax(8rem, 1fr)'), '5rem'])

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
}
</script>

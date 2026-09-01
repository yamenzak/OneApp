<template>
  <!--
    The board: one column per value of a field, and a card in the column its
    record names.

    A board is not a different list. It is the same rows, the same filters, the
    same order and the same selection as every other body — the shell above
    owns all of that — drawn as columns instead of as lines.

    Which field is the reader's, and so is what a card says. A screen declares
    the one a board *opens* on; from there "show me this by assignee instead"
    is the same kind of question as "sort by this column", and it is answered
    the same way — changed in the settings dialog, kept in a saved view.

    Two kinds of field make columns, and they make them differently:

      * A **Select** becomes its own options, in the doctype's own order,
        coloured and glyphed by the doctype's own Document States. Every option
        gets a column whether or not anything is in it, because an empty column
        is where you drop something.
      * A **Link** becomes the values actually on the page, drawn as records —
        a face and a name, the same rendering a link cell uses. Not every row
        of the target doctype: a board by assignee in a workspace of four
        hundred people is four hundred columns, and 397 of them are empty.

    Moving a card writes one field. That is the whole interaction, and it is
    the reason a board is worth having over a list: the field people change
    most is the one that otherwise costs a dialog to change.
  -->
  <div class="min-h-0 flex-1 overflow-x-auto overflow-y-hidden">
    <div class="flex h-full items-stretch gap-3 p-3">
      <section
        v-for="column in columns"
        :key="column.value"
        class="flex h-full w-72 shrink-0 flex-col rounded-6 bg-surface-gray-1"
        :data-oneapp-column="column.value"
        @dragover.prevent="over = column.value"
        @dragleave="over === column.value && (over = '')"
        @drop.prevent="drop(column)"
      >
        <!-- The column's own heading: what it is, and how many are in it. The
             badge is the same one the cell draws, so a card's status and its
             column read as the same fact rather than as two. -->
        <header class="flex items-center gap-2 px-3 pt-3 pb-2">
          <!-- A record where the field is a Link, a badge where it is a
               Select. The same two renderings the cells in the list use, so a
               column heading and the value under it are the same thing said
               twice rather than two different things. -->
          <RecordChip v-if="column.record" :record="column.record" compact class="min-w-0" />
          <Badge v-else :theme="column.theme" variant="subtle" size="md">
            <template #prefix>
              <Icon :name="column.icon" class="size-3" />
            </template>
            {{ column.label }}
          </Badge>
          <span class="text-p-xs text-ink-gray-5">{{ column.cards.length }}</span>
          <span class="flex-1" />
          <Button
            v-if="spec.can_create"
            variant="ghost"
            size="sm"
            icon="lucide-plus"
            :label="`New in ${column.label}`"
            :tooltip="`New in ${column.label}`"
            @click="emit('new', { [field]: column.value })"
          />
        </header>

        <!--
          The cards. `overscroll-contain` so reaching the end of one column
          does not start scrolling the board sideways under the reader's
          finger, which is the thing that makes a board of columns feel broken
          on a trackpad.
        -->
        <div
          class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain px-3 pb-3"
          :class="over === column.value && dragging ? 'ring-2 ring-outline-gray-3' : ''"
        >
          <article
            v-for="row in column.cards"
            :key="row.name"
            class="cursor-pointer rounded-6 bg-surface-elevation-1 shadow-sm"
            :class="dragging === row.name ? 'opacity-50' : ''"
            draggable="true"
            @dragstart="start(row)"
            @dragend="end"
            @click="emit('open', row)"
          >
            <RecordCard
              shape="tile"
              :record="identity(row)"
              :fields="cardFields(row)"
              :links="row._links || {}"
              :states="spec.states || []"
            />
          </article>

          <p
            v-if="!column.cards.length"
            class="rounded-6 border border-dashed border-outline-gray-2 px-3 py-6 text-center text-p-sm text-ink-gray-4"
          >
            Nothing here
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Icon } from '@/ui'
import RecordCard from './RecordCard.vue'
import RecordChip from './RecordChip.vue'
import { valueIcon, valueTheme } from '../../lib/fields'
import { plainText } from '../../lib/format'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /** The columns the rows actually came back with, as the picker left them. */
  columns: { type: Array, default: () => [] },
  orderBy: { type: String, default: '' },
  favourites: { type: Boolean, default: false },
  counted: { type: String, default: '' },
  groupBy: { type: String, default: '' },
  /**
   * Which field the columns are and what a card says, as the last page came
   * back for it. The shell owns this because it owns the request: the reader
   * changes it, the rows are fetched again with the new field in them, and the
   * board redraws when they arrive rather than before.
   */
  board: { type: Object, default: () => ({}) },
})

// Declared so the shell can bind one set of props to every body. A board does
// not tick rows — the card is the control, and a checkbox on it would compete
// with the drag for the same pointer.
defineModel('selection', { type: Array, default: () => [] })

const emit = defineEmits(['open', 'like', 'sort', 'favourites', 'change', 'new'])

// Which field the columns are, resolved by the server: the screen's own
// answer, or the manifest's, or this reader's saved one. Checked there against
// both the column list and the fieldtype, so a board is never made of a Date.
const board = computed(() => props.board || {})
const field = computed(() => board.value.column_field || '')

// The field's own definition, from every column the record may show rather
// than from the ones on screen: a reader who hid the status column has not
// stopped it from being what the board is made of.
const definition = computed(() =>
  (props.spec?.all_columns || []).find((c) => c.fieldname === field.value),
)

const isLink = computed(() => definition.value?.fieldtype === 'Link')

// The column values.
//
// A Select's are its own options, in the doctype's order — or alphabetically,
// where the field says the desk sorts them, because `sort_options` is exactly
// this question and the answer should not differ between two surfaces.
//
// A Link has no options to read, so its columns are the values on the page,
// in the order the rows arrived. That is a real difference and worth naming:
// a Select's empty column is still a column you can drop into, and a Link's
// only appears once something is in it.
const values = computed(() => {
  if (isLink.value) {
    return [...new Set(
      props.rows.map((row) => String(row[field.value] || '')).filter(Boolean),
    )]
  }
  const options = String(definition.value?.options || '')
    .split('\n')
    .map((one) => one.trim())
    .filter(Boolean)
  return definition.value?.sort_options ? [...options].sort() : options
})

// What a link column is called, and whose face is on it. The rows carry their
// links already resolved — the same `_links` a cell reads — so this is a
// lookup rather than a second request.
const linkRecord = (value) => {
  for (const row of props.rows) {
    const found = (row._links || {})[field.value]
    if (found && found.value === value) return found
  }
  return { value, label: value }
}

// A record whose status is empty, or is a value the field no longer offers,
// still has to be somewhere: a card that vanishes because somebody edited the
// doctype is worse than an extra column. Only drawn when something is in it.
const strays = computed(() => {
  const known = new Set(values.value)
  return [...new Set(
    props.rows.map((row) => String(row[field.value] || '')).filter((v) => !known.has(v)),
  )]
})

const columns = computed(() =>
  [...values.value, ...strays.value].map((value) => ({
    value,
    label: value || 'None',
    record: isLink.value && value ? linkRecord(value) : null,
    theme: valueTheme(value, props.spec?.states || []),
    icon: valueIcon(value, props.spec?.states || []) || 'lucide-tag',
    cards: props.rows.filter((row) => String(row[field.value] || '') === value),
  })),
)

// What a card says about its record, which is the identity the chip everywhere
// else draws: a face, the title, and the id under it when the title is not
// already the id.
const identity = (row) => {
  const title = props.spec?.title_field
  const label = (title && row[title]) || row.name
  return {
    value: row.name,
    label: String(label),
    id: plainText(String(label)) === row.name ? '' : row.name,
    image: props.spec?.image_field ? row[props.spec.image_field] : null,
  }
}

// The few fields under the title. The reader's own columns, minus the three
// the card already shows in its own way — the title, the status the column
// itself is, and the activity column, which is a row's meta and not a field.
//
// Capped, because a card is a glance. Somebody who wants the fifth field is
// looking at a record rather than at a board.
const META_FIELD = '__activity'
const CARD_FIELDS = 4

// What a card says, in order.
//
// The reader's own list where they have made one, and otherwise the columns
// they are looking at minus the three the card already shows in its own way:
// the title, the field the column itself is, and the activity column, which is
// a row's meta rather than a field.
//
// Chosen fields are not filtered that way. Somebody who puts the status on the
// card meant to put it there.
const shown = computed(() => {
  const chosen = board.value.card_fields || []
  const offered = props.spec?.all_columns || props.columns || []
  if (chosen.length) {
    return chosen
      .map((name) => offered.find((c) => c.fieldname === name))
      .filter(Boolean)
  }
  return (props.columns || []).filter(
    (c) =>
      c.fieldname !== META_FIELD &&
      c.fieldname !== field.value &&
      c.fieldname !== (props.spec?.title_field || 'name') &&
      c.fieldname !== 'name' &&
      c.list_ok !== false,
  )
})

// A blank field is not on the card at all.
//
// A list draws an em dash for an empty cell because the column above it says
// what is missing; a card has no column headers, so the dash says only "there
// is a field here and it is empty", four times over. Frappe's own kanban card
// does the same — what is on it is what is filled in.
//
// Which is also why the cap comes after: capping first and then dropping
// blanks gave one card four fields and the next one none, from the same list.
const cardFields = (row) =>
  shown.value
    .map((c) => ({ ...c, value: row[c.fieldname] }))
    .filter((c) => c.value !== null && c.value !== undefined && c.value !== '')
    .slice(0, CARD_FIELDS)

// --- moving a card ----------------------------------------------------------
//
// Native drag and drop rather than a library: the whole interaction is "pick a
// card up, put it in a column", the browser already ships it, and a drag
// library is a dependency that has to be kept current forever for one screen.

const dragging = ref('')
const over = ref('')

const start = (row) => {
  dragging.value = row.name
}

const end = () => {
  dragging.value = ''
  over.value = ''
}

const drop = (column) => {
  const name = dragging.value
  end()
  if (!name) return
  const row = props.rows.find((one) => one.name === name)
  // Dropped back where it came from. Not a save: a write that changes nothing
  // still bumps `modified`, which moves the card in a list sorted by it.
  if (!row || String(row[field.value] || '') === column.value) return
  emit('change', { row, field: field.value, value: column.value })
}
</script>

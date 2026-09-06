<template>
  <!--
    The board: one column per value of a field, and a card in the column its
    record names.

    A board is not a different list. Same rows, same filters, same order, same
    selection — the shell above owns all of that — drawn as columns.

    Two kinds of field make columns, and differently. A **Select** becomes its
    own options in the doctype's order, coloured by its Document States, and
    every option gets a column whether or not anything is in it, because an
    empty column is where you drop something. A **Link** becomes the values
    actually on the page: a board by assignee over four hundred people would
    otherwise be four hundred columns, 397 of them empty.

    Moving a card writes one field, which is the reason a board is worth having
    over a list.
  -->
  <div class="min-h-0 flex-1 overflow-x-auto overflow-y-hidden">
    <div class="flex h-full items-stretch gap-3 p-3">
      <section
        v-for="(column, at) in columns"
        :key="column.value"
        class="flex h-full w-72 shrink-0 flex-col rounded-6 bg-surface-gray-1"
        :data-oneapp-column="column.value"
        @dragover.prevent="over = column.value"
        @dragleave="over === column.value && (over = '')"
        @drop.prevent="drop(column)"
      >
        <!-- The column's heading: what it is, and how many are in it. The
             badge is the one the cell draws, so a card's status and its column
             read as the same fact. -->
        <header class="flex items-center gap-2 px-3 pt-3 pb-2">
          <!-- A record where the field is a Link, a badge where it is a
               Select — the two renderings the list's cells use. -->
          <RecordChip v-if="column.record" :record="column.record" compact class="min-w-0" />
          <Badge v-else :theme="column.theme" variant="subtle" size="md">
            <template #prefix>
              <Icon :name="column.icon" class="size-3" />
            </template>
            {{ column.label }}
          </Badge>
          <span class="text-p-xs text-ink-gray-5">{{ column.cards.length }}</span>
          <span class="flex-1" />
          <!--
            What this reader has done to the column itself: where it sits, what
            colour it is, and whether they want to see it. Frappe keeps the same
            four facts on a Kanban Board doctype; here they are a *view* — see
            `oneapp_core/board.py`.
          -->
          <Popover v-if="!column.stray">
            <template #trigger>
              <Button
                icon="lucide-ellipsis"
                variant="ghost"
                size="sm"
                data-slot="column-menu"
                :label="`Arrange ${column.label}`"
                :tooltip="`Arrange ${column.label}`"
              />
            </template>
            <template #default>
              <div class="flex w-56 flex-col gap-2 p-2">
                <span class="px-1 text-p-xs text-ink-gray-5">Colour</span>
                <div class="flex flex-wrap gap-1 px-1">
                  <!--
                    A filled circle per colour. `Button` and not a bare swatch:
                    a raw `<button>` anywhere near a card is how the tile
                    stopped being clickable — see
                    `test_a_card_is_mapped_in_one_place`.
                  -->
                  <Button
                    v-for="one in THEMES"
                    :key="one"
                    variant="ghost"
                    size="sm"
                    :icon="column.theme === one ? 'lucide-circle-check-big' : 'lucide-circle'"
                    :class="INK[one]"
                    :data-slot="`column-colour-${one}`"
                    :label="`Colour ${column.label} ${one}`"
                    :tooltip="one"
                    @click="paint(column, one)"
                  />
                </div>
                <div class="flex flex-col gap-0.5 pt-1">
                  <Button
                    variant="ghost"
                    class="justify-start"
                    icon-left="lucide-arrow-left"
                    label="Move left"
                    :disabled="at === 0"
                    @click="shift(at, -1)"
                  />
                  <Button
                    variant="ghost"
                    class="justify-start"
                    icon-left="lucide-arrow-right"
                    label="Move right"
                    :disabled="at === columns.length - 1"
                    @click="shift(at, 1)"
                  />
                  <!-- Archived, not deleted: the records are untouched and the
                       value is still a value. -->
                  <Button
                    variant="ghost"
                    class="justify-start"
                    icon-left="lucide-archive"
                    data-slot="column-archive"
                    label="Archive this column"
                    @click="archive(column)"
                  />
                </div>
              </div>
            </template>
          </Popover>
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
          The cards. `overscroll-contain` so reaching the end of one column does
          not start scrolling the board sideways under the reader's finger.
        -->
        <div
          class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain px-3 pb-3"
          :class="over === column.value && dragging ? 'ring-2 ring-outline-gray-3' : ''"
        >
          <article
            v-for="row in column.cards"
            :key="row.name"
            :data-oneapp-card="row.name"
            class="cursor-pointer rounded-6 bg-surface-elevation-1 shadow-sm"
            :class="[
              dragging === row.name ? 'opacity-50' : '',
              overCard === row.name && dragging && dragging !== row.name
                ? 'ring-2 ring-outline-gray-3'
                : '',
            ]"
            draggable="true"
            @dragstart="start(row)"
            @dragend="end"
            @dragover.stop.prevent="overCard = row.name"
            @click="emit('open', row)"
          >
            <RecordCard
              shape="tile"
              :record="identity(row)"
              :fields="cardFields(row)"
              :links="row._links || {}"
              :states="spec.states || []"
              :meta="row._meta || null"
              :people="row._assigned || []"
              @open="emit('open', row)"
              @like="emit('like', row)"
            />
          </article>

          <p
            v-if="!column.cards.length"
            class="rounded-6 border border-dashed border-outline-gray-2 px-3 py-6 text-center text-p-sm text-ink-gray-4"
          >
            Nothing here
          </p>

          <!--
            A card without a dialog. A modal with the doctype's whole form is
            the wrong weight for "and then call the glazier": a name and Enter,
            everything else one click away.

            Only where the screen has a title field to write — a doctype named
            by a series has nothing a single box could fill in.
          -->
          <TextInput
            v-if="canQuickAdd"
            :model-value="adding[column.value] || ''"
            :data-slot="`quick-add-${column.value}`"
            type="text"
            :placeholder="`New ${spec.singular || 'record'}`"
            :disabled="creating === column.value"
            @update:model-value="adding[column.value] = $event"
            @keydown.enter="quickAdd(column)"
          />
        </div>
      </section>

      <!-- What was archived, and the way back: a column somebody cannot find
           again is a column they lost. -->
      <section v-if="archived.length" class="flex h-full w-56 shrink-0 flex-col gap-2 p-1">
        <span class="px-2 text-p-xs text-ink-gray-5">Archived</span>
        <Button
          v-for="value in archived"
          :key="value"
          variant="subtle"
          class="justify-start"
          icon-left="lucide-archive-restore"
          :data-slot="`column-restore-${value}`"
          :label="value || 'None'"
          @click="restore(value)"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Badge, Button, Icon, Popover, TextInput } from '@/ui'
import RecordCard from './RecordCard.vue'
import RecordChip from '../record/RecordChip.vue'
import { cardIdentity, cardShown, cardValues } from '@/lib/screen/cards'
import { valueIcon, valueTheme } from '@/lib/screen/fields'

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
   * Which field the columns are, as the last page came back for it. The shell
   * owns this because it owns the request: the rows are fetched again with the
   * new field in them, and the board redraws when they arrive.
   */
  board: { type: Object, default: () => ({}) },
  /** What a card says, the same way and for the same reason. */
  cards: { type: Object, default: () => ({}) },
})

// Declared so the shell can bind one set of props to every body. A board does
// not tick rows — the card is the control, and a checkbox would compete with
// the drag for the same pointer.
defineModel('selection', { type: Array, default: () => [] })

const emit = defineEmits([
  'open', 'like', 'sort', 'favourites', 'change', 'new', 'quick', 'changed',
])

/**
 * The colours a column may be, and the swatch each draws.
 *
 * frappe-ui's Badge themes, the same closed set `STATE_COLORS` maps Frappe's
 * colour names onto; `board.THEMES` on the server refuses anything else.
 * Written out rather than built from the name: Tailwind needs the class in the
 * source to emit it.
 */
const THEMES = ['gray', 'blue', 'green', 'orange', 'red', 'amber', 'violet', 'pink', 'teal']

const INK = {
  gray: 'text-ink-gray-5',
  blue: 'text-ink-blue-3',
  green: 'text-ink-green-3',
  orange: 'text-ink-orange-3',
  red: 'text-ink-red-3',
  amber: 'text-ink-amber-3',
  violet: 'text-ink-violet-3',
  pink: 'text-ink-pink-3',
  teal: 'text-ink-teal-3',
}

// Which field the columns are, resolved by the server against both the column
// list and the fieldtype, so a board is never made of a Date.
const board = computed(() => props.board || {})
const field = computed(() => board.value.column_field || '')

// The field's own definition, from every column the record may show rather than
// from the ones on screen: hiding the status column has not stopped it being
// what the board is made of.
const definition = computed(() =>
  (props.spec?.all_columns || []).find((c) => c.fieldname === field.value),
)

const isLink = computed(() => definition.value?.fieldtype === 'Link')

// The column values.
//
// A Select's are its own options, in the doctype's order — or alphabetically
// where `sort_options` says so. A Link has no options to read, so its columns
// are the values on the page: a Select's empty column is still one you can drop
// into, and a Link's only appears once something is in it.
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
// links already resolved, so this is a lookup rather than a second request.
const linkRecord = (value) => {
  for (const row of props.rows) {
    const found = (row._links || {})[field.value]
    if (found && found.value === value) return found
  }
  return { value, label: value }
}

// A record whose status is empty, or is a value the field no longer offers,
// still has to be somewhere. Only drawn when something is in it.
const strays = computed(() => {
  const known = new Set(values.value)
  return [...new Set(
    props.rows.map((row) => String(row[field.value] || '')).filter((v) => !known.has(v)),
  )]
})

/**
 * What this reader has done to the board itself, as the server kept it: the
 * order of the columns, their colours, which are archived, and the order of the
 * cards inside them — keyed by column *value*, because a column is a Select
 * option or a Link id. See `oneapp_core/board.py`.
 */
const arrangement = computed(() => board.value.arrangement || {})

const archived = computed(() => {
  const known = new Set([...values.value, ...strays.value])
  // Only the ones that are still values, or a column archived and then removed
  // from the doctype would sit in the Archived rail forever.
  return (arrangement.value.hidden || []).filter((one) => known.has(one))
})

/** The order the cards sit in, where somebody has arranged them. */
const arrange = (value, cards) => {
  const wanted = (arrangement.value.cards || {})[value]
  if (!wanted?.length) return cards
  const at = new Map(wanted.map((name, index) => [name, index]))
  // A card not in the list sorts after the ones that are, in the order the page
  // came back in.
  return [...cards].sort(
    (a, b) => (at.has(a.name) ? at.get(a.name) : Infinity)
      - (at.has(b.name) ? at.get(b.name) : Infinity),
  )
}

const columns = computed(() => {
  const hidden = new Set(arrangement.value.hidden || [])
  const strayValues = new Set(strays.value)
  const built = [...values.value, ...strays.value]
    .filter((value) => !hidden.has(value))
    .map((value) => ({
      value,
      label: value || 'None',
      stray: strayValues.has(value),
      record: isLink.value && value ? linkRecord(value) : null,
      theme: (arrangement.value.colours || {})[value]
        || valueTheme(value, props.spec?.states || []),
      icon: valueIcon(value, props.spec?.states || []) || 'lucide-tag',
      cards: arrange(value, props.rows.filter(
        (row) => String(row[field.value] || '') === value,
      )),
    }))

  const wanted = arrangement.value.order || []
  if (!wanted.length) return built
  const at = new Map(wanted.map((value, index) => [value, index]))
  // Same rule as the cards: a column nobody placed sits after the ones that
  // were, in the doctype's own order — so a Select that gains an option shows
  // it rather than hiding it behind an order written before it existed.
  return [...built].sort(
    (a, b) => (at.has(a.value) ? at.get(a.value) : Infinity)
      - (at.has(b.value) ? at.get(b.value) : Infinity),
  )
})

// --- arranging ---------------------------------------------------------------
//
// Every one of these writes the whole arrangement back through the same door a
// filter uses: an unsaved change on the shell, saved into a view by the same
// button. Nothing here is a request of its own.

const rearrange = (changes) => {
  emit('changed', { arrangement: { ...arrangement.value, ...changes } })
}

const paint = (column, theme) => {
  rearrange({ colours: { ...(arrangement.value.colours || {}), [column.value]: theme } })
}

const archive = (column) => {
  rearrange({ hidden: [...new Set([...(arrangement.value.hidden || []), column.value])] })
}

const restore = (value) => {
  rearrange({ hidden: (arrangement.value.hidden || []).filter((one) => one !== value) })
}

const shift = (at, by) => {
  const order = columns.value.map((one) => one.value)
  const to = at + by
  if (to < 0 || to >= order.length) return
  ;[order[at], order[to]] = [order[to], order[at]]
  // The archived ones keep their place in the order too: unarchiving should put
  // a column back where it was rather than at the end.
  rearrange({ order: [...order, ...(arrangement.value.hidden || [])] })
}

// --- a card without a dialog -------------------------------------------------

const adding = reactive({})
const creating = ref('')

// A doctype named by a series has nothing one box could fill in, and a screen
// that may not create has nothing to offer.
const canQuickAdd = computed(() => {
  const title = props.spec?.title_field
  if (!props.spec?.can_create || !title) return false
  return (props.spec?.all_columns || []).some(
    (one) => one.fieldname === title && one.editable,
  )
})

const quickAdd = async (column) => {
  const said = String(adding[column.value] || '').trim()
  if (!said || creating.value) return
  creating.value = column.value
  try {
    await new Promise((done, fail) => {
      emit('quick', {
        values: { [props.spec.title_field]: said, [field.value]: column.value },
        done,
        fail,
      })
    })
    adding[column.value] = ''
  } catch {
    // The shell said so with a toast. What was typed stays in the box, which is
    // the only place it exists.
  } finally {
    creating.value = ''
  }
}

// What a card says about its record, from the shared card — a board card and a
// grid card are the same card, see `lib/screen/cards.js`. The board's only
// contribution is dropping the field its columns are made of, which a heading
// already says, and the cap: a column is 18rem wide and a card in one is a
// glance.
const CARD_FIELDS = 4

const identity = (row) => cardIdentity(row, props.spec)

const shown = computed(() =>
  cardShown({
    spec: props.spec,
    columns: props.columns,
    chosen: props.cards?.card_fields || [],
    exclude: [field.value],
  }),
)

const cardFields = (row) => cardValues(row, shown.value, CARD_FIELDS)

// --- moving a card ----------------------------------------------------------
//
// Native drag and drop rather than a library: the whole interaction is "pick a
// card up, put it in a column", and the browser already ships it.

const dragging = ref('')
const over = ref('')
const overCard = ref('')

const start = (row) => {
  dragging.value = row.name
}

const end = () => {
  dragging.value = ''
  over.value = ''
  overCard.value = ''
}

const drop = (column) => {
  const name = dragging.value
  const above = overCard.value
  end()
  if (!name) return
  const row = props.rows.find((one) => one.name === name)
  if (!row) return

  const moved = String(row[field.value] || '') !== column.value
  if (moved) emit('change', { row, field: field.value, value: column.value })

  // Where in the column, which is a different fact from which column and is
  // remembered rather than written to the record.
  //
  // Dropped back exactly where it came from is not a change of either kind: a
  // write that changes nothing still bumps `modified`.
  const now = column.cards.map((one) => one.name).filter((one) => one !== name)
  const at = above && above !== name ? now.indexOf(above) : -1
  const next = at < 0 ? [...now, name] : [...now.slice(0, at), name, ...now.slice(at)]
  const was = (arrangement.value.cards || {})[column.value] || []
  if (!moved && was.length === next.length && was.every((one, i) => one === next[i])) return

  rearrange({ cards: { ...(arrangement.value.cards || {}), [column.value]: next } })
}
</script>

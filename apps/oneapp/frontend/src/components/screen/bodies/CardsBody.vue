<template>
  <!--
    The grid: the same records as the list, each drawn as a card.

    A board and a grid are one card twice. A board buckets its cards by a field
    and lets you drag one from bucket to bucket; a grid lays the same cards out
    flat, in the order the list is sorted by. That is the whole difference, and
    it is the reason this file is short: everything about *what a card says*
    lives in `lib/cards.js`, shared, and everything about which rows there are
    belongs to the shell above.

    Which is also why a grid is not "a board with one column". A board answers
    "where does each of these stand"; a grid answers "show me these as things
    rather than as lines" — a screen of records with pictures, or one whose
    fields are too few to be worth a table. Grouping a grid would make it a
    board, so it does not.

    And where the records *have* pictures, the grid is a gallery: the picture
    across the top of the card and everything else as its caption. That is the
    one place the two views deliberately differ, and it is decided by the
    doctype rather than by a setting — `image_field` is Frappe's own answer to
    "what does one of these look like", and a screen over a doctype that has
    one is a screen worth looking at rather than reading.

    A board does not do this, and that is not an oversight. A board column is
    18rem wide and a card in one is a glance at where a record stands; a column
    of squares is a board you scroll all afternoon.
  -->
  <div class="min-h-0 flex-1 overflow-y-auto p-3">
    <!--
      As many columns as fit, rather than a count per breakpoint. A breakpoint
      asks the *window* how wide it is, and this pane is not the window: open a
      record beside the grid and four columns keep their count in half the
      room, which is four cards of ellipsis. `auto-fill` asks the box the cards
      are actually in, so opening the pane drops the grid to two columns and
      closing it puts them back.
    -->
    <div class="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-3">
      <!--
        The tile is a click surface rather than a control, the same way a list
        row is: the whole card opens the record, and the title inside it is the
        button that makes that reachable from a keyboard. A `<button>` around
        the whole card cannot hold the heart the meta band ends with — a button
        inside a button is not a thing a browser will render.
      -->
      <article
        v-for="row in rows"
        :key="row.name"
        :data-oneapp-card="row.name"
        class="cursor-pointer rounded-6 bg-surface-elevation-1 shadow-sm"
        @click="emit('open', row)"
      >
        <RecordCard
          shape="tile"
          :record="identity(row)"
          :fields="cardFields(row)"
          :links="row._links || {}"
          :states="spec.states || []"
          :cover="!!spec.image_field"
          :meta="row._meta || null"
          :people="row._assigned || []"
          @open="emit('open', row)"
          @like="emit('like', row)"
        />
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import RecordCard from './RecordCard.vue'
import { cardIdentity, cardShown, cardValues } from '../../../lib/cards'

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
  board: { type: Object, default: () => ({}) },
  /**
   * What a card says, as the last page came back for it — the shell owns it
   * because choosing a field changes what is fetched, and a card drawn from
   * the screen's answer while rows arrive for a different one is a card of
   * empty fields for as long as the request takes.
   */
  cards: { type: Object, default: () => ({}) },
})

// Declared so the shell can bind one set of props to every body. A grid does
// not tick rows: a checkbox on a card is a second target competing with the
// card itself, which is the whole control.
defineModel('selection', { type: Array, default: () => [] })

const emit = defineEmits(['open', 'like', 'sort', 'favourites', 'change', 'new'])

// More than a board card carries, and for one reason: a board card sits in a
// column 18rem wide beside two dozen others, and a grid card has a quarter of
// the pane to itself. Still the server's own cap — a card past this is a
// record rendered badly, and whoever wants the seventh field wants the record.
const CARD_FIELDS = 6

const identity = (row) => cardIdentity(row, props.spec)

// No exclusion here, unlike a board: there is no column heading above a grid
// card saying a field twice.
const shown = computed(() =>
  cardShown({
    spec: props.spec,
    columns: props.columns,
    chosen: props.cards?.card_fields || [],
  }),
)

const cardFields = (row) => cardValues(row, shown.value, CARD_FIELDS)
</script>

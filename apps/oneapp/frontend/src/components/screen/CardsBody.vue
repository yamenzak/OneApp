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
        A card is a link to its record, so it is a button: a div with a click
        handler is invisible to a keyboard and to anything reading the page
        aloud, and a grid of forty of them is forty records nobody can reach.
        `text-left` because a button centres its content by default and a card
        is a paragraph, not a label.
      -->
      <button
        v-for="row in rows"
        :key="row.name"
        type="button"
        :data-oneapp-card="row.name"
        class="rounded-6 bg-surface-elevation-1 text-left shadow-sm ring-outline-gray-2 hover:ring-1 focus-visible:ring-2"
        @click="emit('open', row)"
      >
        <RecordCard
          shape="tile"
          :record="identity(row)"
          :fields="cardFields(row)"
          :links="row._links || {}"
          :states="spec.states || []"
        />
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import RecordCard from './RecordCard.vue'
import { cardIdentity, cardShown, cardValues } from '../../lib/cards'

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

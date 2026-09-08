<template>
  <!--
    The grid: the same records as the list, each drawn as a card.

    A board and a grid are one card twice — a board buckets its cards by a
    field, a grid lays them out flat in the list's own order. Which is why this
    file is short: what a card *says* lives in `lib/screen/cards.js`, and which
    rows there are belongs to the shell.

    A grid is not "a board with one column". A board answers "where does each of
    these stand"; a grid answers "show me these as things rather than as lines".
    Grouping a grid would make it a board, so it does not.

    Where the records have pictures the grid is a gallery: the picture across
    the top and everything else as its caption, decided by the doctype's
    `image_field` rather than by a setting. A board does not do this, and that
    is not an oversight — a board column is 18rem wide, and a column of squares
    is a board you scroll all afternoon.
  -->
  <div class="min-h-0 flex-1 overflow-y-auto p-3">
    <!--
      As many columns as fit, rather than a count per breakpoint: a breakpoint
      asks the *window* how wide it is, and this pane is not the window.
      `auto-fill` asks the box the cards are actually in.
    -->
    <div class="grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-3">
      <!--
        The tile is a click surface rather than a control, the same way a list
        row is, and the title inside it is the button that makes it reachable
        from a keyboard. A `<button>` around the whole card cannot hold the
        heart the meta band ends with.
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
import RecordCard from '@/modules/onespace/components/screen/bodies/RecordCard.vue'
import { cardIdentity, cardShown, cardValues } from '@/modules/onespace/lib/screen/cards'

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
   * because choosing a field changes what is fetched.
   */
  cards: { type: Object, default: () => ({}) },
})

// Declared so the shell can bind one set of props to every body. A grid does
// not tick rows: a checkbox on a card competes with the card itself.
defineModel('selection', { type: Array, default: () => [] })

const emit = defineEmits(['open', 'like', 'sort', 'favourites', 'change', 'new'])

// More than a board card carries: a board card sits in a column 18rem wide, a
// grid card has a quarter of the pane. Still the server's own cap — whoever
// wants the seventh field wants the record.
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

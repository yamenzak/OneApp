<template>
  <!--
    One record, as a card. The hover card over a link, the card on a board and
    the card in a grid are the same thing: an identity, then the few fields
    worth reading without opening the record.

    Which few is not ours to choose — `in_preview` is a flag a doctype sets on
    its own fields, once, and every surface pointing at that doctype gets the
    same answer. That is what makes a board card good for free: a doctype whose
    author marked three fields worth previewing already described its card.

    Two shapes rather than two components, because the difference is only how
    much room there is:

      * `panel` — a hover card. Labels in a narrow column of their own, because
        five stacked label/value pairs read as ten unrelated lines and the same
        five in two columns read as a record.
      * `tile` — a board or grid card. No labels: three bands — who it is, what
        it says, and how it is doing — separated by hairlines, which is what
        Frappe CRM's kanban card is and it is right. Values stack one per line
        rather than wrapping into a paragraph: a card of five values run
        together is a sentence nobody wrote, and a column of five is a record.
  -->
  <div :class="frame">
    <!--
      Panel: not a control. Nothing on a hover card is pressable — it is what
      appears *because* you are already pointing at the link.
    -->
    <div v-if="isPanel" class="p-3">
      <RecordChip :record="record" />
    </div>

    <!--
      Tile: the card's one keyboard target, and its accessible name. The card
      itself is a click surface — the whole tile opens the record, the same way
      a list row does — and a click surface is not reachable by keyboard, so the
      title is the real control. Exactly the arrangement the list already uses:
      the row is a div, the title inside it is a button.

      `.stop` because the tile's own handler would otherwise fire too and open
      the record twice.
    -->
    <button
      v-else
      type="button"
      class="flex min-w-0 text-left"
      @click.stop="emit('open')"
    >
      <RecordChip :record="record" />
    </button>

    <Divider v-if="isPanel && (loading || fields.length)" />

    <div v-if="isPanel" class="p-3">
      <LoadingText v-if="loading" text="Loading" />

      <!-- A hover card: labels beside values. -->
      <dl
        v-else-if="fields.length"
        class="grid grid-cols-[7rem_1fr] items-baseline gap-x-3 gap-y-2"
      >
        <template v-for="field in fields" :key="field.fieldname">
          <dt class="truncate text-p-sm text-ink-gray-5">{{ field.label }}</dt>
          <dd class="flex min-w-0 items-center">
            <FieldCell
              :column="field"
              :value="field.value"
              :states="states"
              :links="links"
            />
          </dd>
        </template>
      </dl>

      <span v-else class="text-p-sm text-ink-gray-5">Nothing else to show.</span>
    </div>

    <!-- A tile: one value per line, each truncated in its own row so a long
         one shortens itself rather than widening the card. -->
    <template v-else-if="fields.length">
      <Divider />
      <div class="flex flex-col gap-2">
        <div
          v-for="field in fields"
          :key="field.fieldname"
          class="flex min-w-0 items-center"
        >
          <FieldCell
            :column="field"
            :value="field.value"
            :states="states"
            :links="links"
            class="min-w-0"
          />
        </div>
      </div>
    </template>

    <!--
      How the record is doing: when it last moved, how many people have said
      something, and whether this one is yours. The same three the list shows at
      the end of every row — they cost nothing to carry, they are already on the
      row, and a card that drops them is a card saying less than the list it
      came from for no reason.

      Only where the caller has them. A hover card is one record fetched on its
      own and has no row meta to show.
    -->
    <template v-if="!isPanel && meta">
      <Divider />
      <RowMeta spread :meta="meta" :people="people" @like="emit('like')" />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Divider, LoadingText } from '@/ui'
import FieldCell from './FieldCell.vue'
import RecordChip from './RecordChip.vue'
import RowMeta from './RowMeta.vue'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  /** `[{ fieldname, label, fieldtype, value, … }]`, already resolved. */
  fields: { type: Array, default: () => [] },
  /** The target doctype's Document States, so a status reads in its colour. */
  states: { type: Array, default: () => [] },
  /**
   * The row's resolved links, keyed by fieldname. A board card draws fields
   * straight off a list row, where a Link is an id and the label for it came
   * back beside it; a hover card's fields arrive already resolved and pass
   * nothing here.
   */
  links: { type: Object, default: () => ({}) },
  /** `row._meta` — when it moved, how many comments, whether it is liked. */
  meta: { type: Object, default: null },
  /** `row._assigned` — who it is on, already resolved to faces and names. */
  people: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  shape: { type: String, default: 'panel' },
})

const emit = defineEmits(['open', 'like'])

// Computed rather than a ternary in the binding. `test_every_class_emits_css`
// reads the string literals out of a `:class` and checks each is a real
// utility, so `shape === 'panel' ? 'p-3' : ''` offered it `panel` and `tile` as
// class names and it rightly said neither emits any CSS.
const isPanel = computed(() => props.shape === 'panel')

// `gap-2.5` is the rhythm the hairlines sit in: the same space above and below
// each one, which is what makes three bands read as three bands.
const frame = computed(() => (isPanel.value ? '' : 'flex flex-col gap-2.5 p-3'))
</script>

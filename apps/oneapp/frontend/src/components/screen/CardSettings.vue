<template>
  <!--
    What a card-shaped view is made of: what a card says, and — where the view
    buckets its cards — which field it buckets them by.

    One dialog for the board and the grid because they are one card twice; the
    difference between them is arrangement, and only the board has an
    arrangement to ask about. See `lib/cards.js`.

    Both answers are the reader's, not the manifest's. A screen declares which
    field a board *opens* on — that is what makes it offerable at all — and
    from there "show me this by assignee instead" is the same kind of question
    as "sort by this column", answered the same way: changed here, kept in a
    saved view.
  -->
  <Dialog v-model="open" :title="title">
    <div class="flex flex-col gap-5 p-1">
      <!--
        A grid has no columns to be of. Its cards are laid out flat, in the
        order the list is sorted by — bucketing them by a field is what makes
        a board, and offering the question here would offer two ways to ask
        for the same view.
      -->
      <Select
        v-if="buckets"
        label="Columns of"
        description="A Select becomes its own options; a Link becomes whoever is on the page."
        :model-value="field"
        :options="fieldOptions"
        @update:model-value="field = $event"
      />

      <div class="flex flex-col gap-2">
        <!--
          The component's own label and description rather than a FormLabel and
          a paragraph beside it: the label is what names the trigger, and a
          hand-built one leaves the control called after its placeholder.

          Bounded, and the server bounds it again. A card is a glance: past half
          a dozen fields it is a record rendered badly, and the person who wants
          the seventh wants the record.
        -->
        <MultiSelect
          label="On each card"
          description="Under the title, in this order. Nothing chosen shows the columns you have on the list."
          :model-value="cardFields"
          :options="cardOptions"
          placeholder="The columns on the list"
          empty-text="No field by that name"
          @update:model-value="pickCards"
        />
        <p v-if="full" class="text-p-xs text-ink-gray-5">
          That is as many as a card carries.
        </p>
      </div>
    </div>

    <template #actions>
      <Button variant="ghost" label="Reset" @click="reset" />
      <Button variant="solid" label="Done" @click="open = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Dialog, MultiSelect, Select } from '@/ui'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** The resolved screen, for the fields a card may carry. */
  spec: { type: Object, required: true },
  /** The board as the last page came back for it — see `BoardBody.board`. */
  board: { type: Object, default: () => ({}) },
  /** What a card says, the same way — see `lib/cards.js`. */
  cards: { type: Object, default: () => ({}) },
  /** Which view is under the gear, because only one of them has buckets. */
  viewType: { type: String, default: 'board' },
})
const emit = defineEmits(['update:modelValue', 'changed'])

// The server's own cap, repeated so the control stops where the save does. A
// picker that accepts a seventh field and drops it is a picker that lies.
const MAX_CARD_FIELDS = 6

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// Only a board arranges its cards by a field. Named for what it is rather
// than checked against a string at each of the three places that ask.
const buckets = computed(() => props.viewType === 'board')

const title = computed(() => (buckets.value ? 'Board settings' : 'Card settings'))

const board = computed(() => props.board || {})

const fieldOptions = computed(() =>
  (board.value.fields || []).map((one) => ({ label: one.label, value: one.fieldname })),
)

// Only what a card can actually draw. A child table is rows and an attachment
// gallery is a strip of pictures; neither is a line under a title.
const cardOptions = computed(() =>
  (props.spec?.list_columns || [])
    .filter((one) => one.fieldname !== '__activity')
    .map((one) => ({ label: one.label, value: one.fieldname })),
)

const field = computed({
  get: () => board.value.column_field || '',
  set: (value) => emit('changed', { column_field: value }),
})

const cardFields = computed(() => props.cards?.card_fields || [])

const full = computed(() => cardFields.value.length >= MAX_CARD_FIELDS)

const pickCards = (chosen) => {
  emit('changed', { card_fields: (chosen || []).slice(0, MAX_CARD_FIELDS) })
}

// Back to what the screen says. Empty rather than the current values: the
// view resolves its own default, and writing that default in as a choice would
// freeze it against a manifest that later changes its mind.
const reset = () =>
  emit('changed', buckets.value ? { column_field: '', card_fields: [] } : { card_fields: [] })
</script>

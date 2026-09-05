<template>
  <!--
    How much of the list you are looking at, and how to see more.

    Frappe CRM's footer, and it earns its place for the same reason theirs
    does: a list that silently stops at its first page reads as "that is all of
    them". The count is real — the server counts what matches, not what it
    sent — so "48 of 1,240" is a fact rather than a guess.
  -->
  <div class="flex shrink-0 items-center gap-3 border-t border-outline-gray-2 px-3 py-2">
    <div class="ms-auto flex items-center gap-2">
      <Button
        v-if="hasMore"
        label="Load more"
        :loading="loading"
        @click="emit('more')"
      />
      <!--
        The count, and how many to fetch — one control, because they are one
        question. Four page-size buttons used to hold the whole left half of
        this row for a number a person sets once and then reads every time, so
        the reading is the control now and the setting is inside it.
      -->
      <Dropdown :options="options" align="end">
        <Button
          data-slot="page-length"
          variant="ghost"
          size="sm"
          icon-right="lucide-chevron-down"
          :label="shown"
          tooltip="How many rows to fetch"
        />
      </Dropdown>
      <!--
        The rows, as a file. Beside the count rather than in a menu behind it:
        "send me that as a spreadsheet" is how a register reaches an accountant
        or a bank, and it was the one thing every list here could not do.

        What comes out is what is on screen — this reader's columns, in their
        order, narrowed by whatever the filters say — which is why it belongs in
        the corner that already answers "how much of this am I looking at".
      -->
      <Button
        data-slot="export"
        icon="lucide-download"
        variant="ghost"
        size="sm"
        :loading="exporting"
        label="Export as CSV"
        tooltip="Export as CSV"
        @click="emit('export')"
      />

      <!--
        Which columns, and how wide. It sat above the table with the filters,
        where it was a fourth control competing with the box people type in —
        and it is not a question about the rows, it is a question about the
        table. Here it is beside the other one of those: how many of them
        there are, and how many to fetch.

        One gear, and what it opens is whatever the body is: a list's columns,
        a card view's card. Both are "what does this show" rather than "which
        rows", which is the question this corner already answers.
      -->
      <Button
        icon="lucide-settings"
        variant="ghost"
        size="sm"
        :label="settingsLabel"
        :tooltip="settingsLabel"
        @click="emit('columns')"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Dropdown } from '@/ui'
import { CARD_VIEW_TYPES } from '../../../lib/viewTypes'

const props = defineProps({
  count: { type: Number, default: 0 },
  // Null while unknown — the count comes with the first page, and a footer
  // reading "48 of 0" until it arrives is worse than one reading "48".
  total: { type: Number, default: null },
  pageLength: { type: Number, default: 100 },
  sizes: { type: Array, default: () => [20, 50, 100, 500] },
  hasMore: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  /** Which body is under it, because the gear opens that body's settings. */
  viewType: { type: String, default: 'list' },
  /** Whether a file is being built, so the button says so rather than nothing. */
  exporting: { type: Boolean, default: false },
})
const emit = defineEmits(['more', 'page-length', 'columns', 'export'])

const number = (value) => value.toLocaleString()

// Named for what it opens. "Choose columns" over a board is a control that
// says the wrong thing about itself — a board has no columns to choose, and a
// grid has neither columns nor buckets.
const settingsLabel = computed(() => {
  if (props.viewType === 'board') return 'Board settings'
  return CARD_VIEW_TYPES.includes(props.viewType) ? 'Card settings' : 'Choose columns'
})

// A tick beside the one in force, and nothing beside the others: a menu of
// four numbers with no mark says which are available and not which you are on.
const options = computed(() =>
  props.sizes.map((size) => ({
    label: `${number(size)} rows`,
    ...(size === props.pageLength ? { icon: 'lucide-check' } : {}),
    onClick: () => emit('page-length', size),
  })),
)

const shown = computed(() =>
  props.total === null || props.total === undefined
    ? `${number(props.count)}`
    : `${number(props.count)} of ${number(props.total)}`,
)
</script>

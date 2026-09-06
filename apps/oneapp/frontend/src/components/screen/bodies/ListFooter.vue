<template>
  <!--
    How much of the list you are looking at, and how to see more. A list that
    silently stops at its first page reads as "that is all of them"; the count
    is real — the server counts what matches, not what it sent.
  -->
  <div class="flex shrink-0 items-center gap-3 border-t border-outline-gray-2 px-3 py-2">
    <div class="ms-auto flex items-center gap-2">
      <Button
        v-if="hasMore"
        :label="__('Load more')"
        :loading="loading"
        @click="emit('more')"
      />
      <!-- The count, and how many to fetch — one control, because they are one
           question. Four page-size buttons used to hold the whole left half of
           this row for a number a person sets once. -->
      <Dropdown :options="options" align="end">
        <Button
          data-slot="page-length"
          variant="ghost"
          size="sm"
          icon-right="lucide-chevron-down"
          :label="shown"
          :tooltip="__('How many rows to fetch')"
        />
      </Dropdown>
      <!--
        The rows, as a file. Beside the count rather than in a menu behind it:
        what comes out is what is on screen — this reader's columns, narrowed by
        whatever the filters say.
      -->
      <Button
        data-slot="export"
        icon="lucide-download"
        variant="ghost"
        size="sm"
        :loading="exporting"
        :label="__('Export as CSV')"
        :tooltip="__('Export as CSV')"
        @click="emit('export')"
      />

      <!--
        Which columns, and how wide. Not a question about the rows, so it sits
        beside the other question about the table rather than above it with the
        filters. One gear, and what it opens is whatever the body is: a list's
        columns, a card view's card.
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
import { __ } from '@/lib/runtime/translate'
import { CARD_VIEW_TYPES } from '@/lib/screen/viewTypes'

const props = defineProps({
  count: { type: Number, default: 0 },
  // Null while unknown — the count comes with the first page, and a footer
  // reading "48 of 0" is worse than one reading "48".
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

// Named for what it opens: "Choose columns" over a board is a control that says
// the wrong thing about itself.
const settingsLabel = computed(() => {
  if (props.viewType === 'board') return __('Board settings')
  return CARD_VIEW_TYPES.includes(props.viewType) ? __('Card settings') : __('Choose columns')
})

// A tick beside the one in force: a menu of four numbers with no mark says
// which are available and not which you are on.
const options = computed(() =>
  props.sizes.map((size) => ({
    label: __('{0} rows', [number(size)]),
    ...(size === props.pageLength ? { icon: 'lucide-check' } : {}),
    onClick: () => emit('page-length', size),
  })),
)

const shown = computed(() =>
  props.total === null || props.total === undefined
    ? `${number(props.count)}`
    : __('{0} of {1}', [number(props.count), number(props.total)]),
)
</script>

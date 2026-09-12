<template>
  <!--
    The full filter panel: anything the quick boxes above cannot say.

    A stack of [field][operator][value] rows, which is Frappe's shape. What a
    person picks here narrows the screen and never widens it, and the server
    checks the same thing again — the operator menu and the allow list it is
    checked against are generated from one table.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <!-- A count belongs in a badge, not inside the word. "Filter (2)" reads
           as a label; a badge reads as a number. -->
      <Button
        :icon="compact ? 'lucide-list-filter' : undefined"
        :icon-left="compact ? undefined : 'lucide-list-filter'"
        :label="__('Filter')"
        :variant="filters.length ? 'subtle' : 'ghost'"
      >
        <template v-if="filters.length && !compact" #suffix>
          <Badge :label="String(filters.length)" theme="blue" variant="subtle" />
        </template>
      </Button>
    </template>

    <template #default>
      <div class="flex w-[min(34rem,90vw)] flex-col gap-3 p-3">
        <p v-if="!draft.length" class="text-p-sm text-ink-muted">
          {{ __('No filters yet. Add one to narrow the list.') }}
        </p>

        <div v-else class="flex flex-col gap-2">
          <FilterRow
            v-for="(filter, index) in draft"
            :key="index"
            :filter="filter"
            :columns="columns"
            :space-code="spaceCode"
            :screen="screen"
            @update:filter="replace(index, $event)"
            @remove="remove(index)"
          />
        </div>

        <div class="flex items-center gap-2 border-t border-outline-gray-1 pt-3">
          <Button
            icon-left="lucide-plus"
            :label="__('Add filter')"
            :disabled="!filterable.length"
            @click="add"
          />
          <Button v-if="draft.length" variant="ghost" :label="__('Clear all')" @click="clear" />
          <Button class="ms-auto" variant="solid" :label="__('Apply')" @click="apply" />
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { Badge, Button, Popover } from '@/ui'
import FilterRow from '@/modules/onespace/components/screen/views/FilterRow.vue'
import { defaultOperator, operatorsFor, valueShape } from '@/modules/onespace/lib/screen/fields'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  // Applied filters, as the screen resolved them.
  filters: { type: Array, default: () => [] },
  columns: { type: Array, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
})
const emit = defineEmits(['changed'])

// Icon and nothing else on a phone, where the word is the thing that does not
// fit. The count goes with it: a badge on a 28px button is a smudge, and the
// filled variant already says there are filters.
//
// Asked here rather than passed in: how a control renders at a width is the
// control's own business.
const compact = useIsMobile()

const open = ref(false)

// Edited here, applied on Apply: a request per keystroke is not a filter.
const draft = ref([])

// A field with no operators at all cannot be filtered — a child table is rows
// rather than a value — so it is not offered as one.
const filterable = computed(() => props.columns.filter((c) => operatorsFor(c).length))

const blank = () => {
  const column = filterable.value[0]
  const operator = defaultOperator(column)
  const shape = valueShape(column, operator)
  const value = shape === 'range' ? ['', ''] : shape === 'multi' ? [] : shape === 'set' ? 'set' : ''
  return [column.fieldname, operator, value]
}

const add = () => {
  draft.value = [...draft.value, blank()]
}

const replace = (index, next) => {
  draft.value = draft.value.map((filter, at) => (at === index ? next : filter))
}

// Removing one applies immediately and leaves the panel open: there is nothing
// left to type into, and a person removing one of three is usually about to
// remove another.
const remove = (index) => {
  draft.value = draft.value.filter((_filter, at) => at !== index)
  emit('changed', draft.value)
}

const clear = () => {
  draft.value = []
  open.value = false
  emit('changed', draft.value)
}

// Apply closes it. The point of asking is to see the answer, and the panel is
// sitting on top of it.
const apply = () => {
  open.value = false
  emit('changed', draft.value)
}

// Seeded from whatever the screen resolved to, so the panel opens showing what
// this person is looking at.
watch(
  () => props.filters,
  (filters) => {
    draft.value = (filters || []).map((filter) => [...filter])
  },
  { immediate: true, deep: true },
)
</script>

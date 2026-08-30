<template>
  <!--
    How much of the list you are looking at, and how to see more.

    Frappe CRM's footer, and it earns its place for the same reason theirs
    does: a list that silently stops at its first page reads as "that is all of
    them". The count is real — the server counts what matches, not what it
    sent — so "48 of 1,240" is a fact rather than a guess.
  -->
  <div class="flex shrink-0 items-center gap-3 border-t border-outline-gray-2 px-3 py-2">
    <!-- `options`, not `buttons`: frappe-ui's TabButtons renamed the prop, and
         an unknown prop on a Vue component is silently an attribute. -->
    <TabButtons
      :model-value="pageLength"
      :options="options"
      size="sm"
      @update:model-value="emit('page-length', $event)"
    />

    <div class="ms-auto flex items-center gap-3">
      <Button
        v-if="hasMore"
        label="Load more"
        :loading="loading"
        @click="emit('more')"
      />
      <span class="whitespace-nowrap text-p-xs tabular-nums text-ink-gray-5">
        {{ shown }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, TabButtons } from '@/ui'

const props = defineProps({
  count: { type: Number, default: 0 },
  // Null while unknown — the count comes with the first page, and a footer
  // reading "48 of 0" until it arrives is worse than one reading "48".
  total: { type: Number, default: null },
  pageLength: { type: Number, default: 100 },
  sizes: { type: Array, default: () => [20, 50, 100, 500] },
  hasMore: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['more', 'page-length'])

const options = computed(() =>
  props.sizes.map((size) => ({ label: String(size), value: size })),
)

const number = (value) => value.toLocaleString()

const shown = computed(() =>
  props.total === null || props.total === undefined
    ? `${number(props.count)}`
    : `${number(props.count)} of ${number(props.total)}`,
)
</script>

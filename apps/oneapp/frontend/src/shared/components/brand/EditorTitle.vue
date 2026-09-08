<template>
  <!--
    The heading of a dialog that is one of our editors.

    The mark, then the product said the way the family is written, then what is
    actually open. In that order because it is the order of the question: a
    person who pressed "Open in OneCode" already knows where they are and needs
    the field's name; a person who arrived some other way needs both.
  -->
  <span class="flex min-w-0 items-center gap-2">
    <BrandMark :name="brand" class="size-5 shrink-0" />
    <SpaceName :brand="brand" class="shrink-0" />
    <template v-if="name">
      <span class="shrink-0 text-ink-gray-3" aria-hidden="true">·</span>
      <span class="truncate">{{ name }}</span>
    </template>
  </span>
</template>

<script setup>
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'

defineProps({
  /** A key of `MARKS`. */
  brand: { type: String, required: true },
  /** What is open in it — a field's label, a sheet's title. */
  name: { type: String, default: '' },
})
</script>

<template>
  <!--
    The mark with its name beside it.

    Two lines, and the small one is the point: every app in this family is a
    One, so "One" is said quietly above the part that differs. Written out it
    is "OneInventory"; drawn it is the mark, "One", and "Inventory" — which
    reads as a family at a glance and as a product at rest.

    The platform's own mark has no second word, so it is the one case that
    draws a single line.
  -->
  <span class="flex items-center gap-2.5" :data-slot="`lockup-${name}`">
    <BrandMark :name="name" :class="markSize" />
    <span v-if="!bare" class="flex min-w-0 flex-col leading-none">
      <span :class="['text-ink-gray-5', smallSize]">{{ FAMILY }}</span>
      <span
        v-if="rest"
        :class="['truncate font-semibold text-ink-gray-8', bigSize]"
      >{{ rest }}</span>
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import { MARKS } from '@/shared/lib/brand/marks'

//: What every app in the family is called before the part that differs. Not
//: translated: it is a name, and a name is the same in every language.
const FAMILY = 'One'

const props = defineProps({
  /** A key of `MARKS`. */
  name: { type: String, required: true },
  /** The mark alone, no words. */
  bare: { type: Boolean, default: false },
  size: { type: String, default: 'md' },
})

/** `OneInventory` → `Inventory`. Empty for the platform's own mark. */
const rest = computed(() => {
  const said = MARKS[props.name]?.name || ''
  return said.startsWith(FAMILY) ? said.slice(FAMILY.length) : said
})

const markSize = computed(() =>
  ({ sm: 'size-5', md: 'size-8', lg: 'size-12', xl: 'size-20' })[props.size] || 'size-8')

const smallSize = computed(() =>
  ({ sm: 'text-[9px]', md: 'text-p-xs', lg: 'text-p-sm', xl: 'text-p-base' })[props.size]
  || 'text-p-xs')

const bigSize = computed(() =>
  ({ sm: 'text-p-xs', md: 'text-p-base', lg: 'text-lg', xl: 'text-2xl' })[props.size]
  || 'text-p-base')
</script>

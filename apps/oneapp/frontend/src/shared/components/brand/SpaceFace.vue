<template>
  <!--
    How a space is drawn, decided once.

    Three answers in order, and the order is the point:

      * the **mark** it names, if it names one — an app of ours, in its own
        colours, recognisable at rail size;
      * the **logo** somebody uploaded, for a space that is a customer's own;
      * the **letter** `Avatar` makes of its label, which is what every space
        had before any of this.

    One component because there are four surfaces — the rail, the launcher, the
    marketplace's cards and the marketplace's list of what you already have —
    and four copies of a three-way choice is four places for a space to look
    like itself in three of them.
  -->
  <BrandMark v-if="mark" :name="space.brand" :class="markClass" />
  <Avatar
    v-else
    :label="space.space_label || space.label || ''"
    :image="space.logo || null"
    shape="square"
    :size="size"
  />
</template>

<script setup>
import { computed } from 'vue'
import { Avatar } from '@/ui'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import { MARKS } from '@/shared/lib/brand/marks'

const props = defineProps({
  /** A space from the manifest, or a marketplace card wearing the same keys. */
  space: { type: Object, required: true },
  /** An `Avatar` size, which the mark is matched to. */
  size: { type: String, default: 'lg' },
})

// Named *and* drawn: a manifest naming a mark this build does not have would
// otherwise render an empty box, which is exactly what the closed Select on
// the doctype exists to prevent and exactly what a stale tenant cache can
// still do between a deploy and a sync.
const mark = computed(() => !!MARKS[props.space?.brand])

const markClass = computed(() =>
  ({ sm: 'size-5', md: 'size-6', lg: 'size-8', xl: 'size-10', '2xl': 'size-12' })[props.size]
  || 'size-8')
</script>

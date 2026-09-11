<!--
  One thing being written, wherever it is being written.

  Every AI surface in this product has the same three seconds to fill and
  there are only three shapes it can take: a **block** where a paragraph is
  landing, an **inline** span where a cell or a field is, and an **overlay**
  where a whole pane is being rewritten. So one component with a mode, not one
  per surface — because three of them would be three animations, three sets of
  colours and three answers to what happens when nothing arrives.

  The animation is a sheen travelling across the thing rather than a spinner
  beside it. A spinner says "the application is busy"; a sheen over the actual
  words says "this text, here, is being written", which is the only fact worth
  drawing. Colour is the one flourish and it is deliberately narrow — two hues
  and a highlight, moving — because "AI is happening" needs to be recognisable
  at a glance across mail, a document and a sheet, and a different palette in
  each would defeat that before it started.

  `prefers-reduced-motion` stops the travel and leaves a static tint. That is
  not a courtesy: a shimmer somebody cannot turn off, on text they are trying
  to read, is a barrier rather than a flourish.
-->
<template>
  <div :class="shape" :data-writing="active ? 'yes' : 'no'" data-slot="ai-glow">
    <!--
      Nothing has arrived yet, and something has to hold the space. Lines
      rather than a spinner, at the width the answer will be, so the page does
      not jump when the first phrase lands.
    -->
    <div v-if="skeleton" class="flex flex-col gap-2" aria-hidden="true">
      <div
        v-for="line in lines"
        :key="line"
        class="oneapp-glow-bar"
        :style="{ width: widths[(line - 1) % widths.length] }"
      />
    </div>

    <slot v-else />

    <!--
      The one thing a screen reader is told. The sheen is decoration and the
      skeleton is decoration; that something is being written, and later that
      it finished, is the content.
    -->
    <span class="sr-only" role="status" aria-live="polite">
      {{ active ? __('Writing') : '' }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Whether something is arriving right now. */
  active: { type: Boolean, default: false },
  /** Nothing has landed yet, so draw the skeleton instead of the slot. */
  empty: { type: Boolean, default: false },
  /**
   * Where this is: a paragraph, a cell, or a whole pane.
   *
   * `overlay` makes the element positioned and paints the sheen over its
   * contents; the other two paint it under the text.
   */
  mode: {
    type: String,
    default: 'block',
    validator: (one) => ['block', 'inline', 'overlay'].includes(one),
  },
  /** Skeleton lines, when there is nothing yet. Ignored inline. */
  lines: { type: Number, default: 3 },
})

// Uneven on purpose: three bars of identical width read as a table, and the
// last line of a paragraph is never full.
const widths = ['100%', '92%', '64%', '84%']

const OVERLAY = 'overlay'
const INLINE = 'inline'

/**
 * Worked out here rather than in the template's class list, so the one place
 * a class name is written is `index.css`. A ternary in the markup would put
 * half of these in the template and half in the stylesheet, and the audit
 * that checks every class emits CSS would be reading the wrong half.
 */
const shape = computed(() => [
  'oneapp-glow',
  `oneapp-glow-${props.mode}`,
  props.active ? 'is-writing' : '',
  props.mode === OVERLAY ? 'relative' : '',
])

/** Nothing has landed, and inline has no room for bars. */
const skeleton = computed(() => props.active && props.empty && props.mode !== INLINE)
</script>

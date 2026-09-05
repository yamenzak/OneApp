<!--
  A line across the conversation with a word on it.

  Two things in a thread are worth saying between messages rather than inside
  one: where the mail somebody has not read begins, and that a run of read
  messages has been folded away. Both are the same shape — a hairline, a label,
  a hairline — so both are this.
-->
<template>
  <div class="flex items-center gap-3">
    <span class="h-0 flex-1 border-t" :class="rule" />
    <!-- The label, or something to press. A folded run needs a control; a
         marker saying "2 new messages" is not one, and dressing it as a button
         invites a click that does nothing. -->
    <slot>
      <Badge :theme="theme" variant="outline" size="lg" :label="label" />
    </slot>
    <span class="h-0 flex-1 border-t" :class="rule" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Badge } from '@/ui'

const props = defineProps({
  /** What the line says. Ignored when the default slot is filled. */
  label: { type: String, default: '' },
  /** `unread` draws it in blue, the colour a new thing is in this product. */
  tone: { type: String, default: 'quiet' },
})

const unread = computed(() => props.tone === 'unread')
const theme = computed(() => (unread.value ? 'blue' : 'gray'))

// In the script rather than in the template: the same ternary written inside
// `:class` puts the bare word `unread` into the stylesheet audit's list of
// classes, and it fails on a class that emits no CSS.
const rule = computed(() =>
  unread.value ? 'border-outline-blue-3' : 'border-outline-gray-2',
)
</script>

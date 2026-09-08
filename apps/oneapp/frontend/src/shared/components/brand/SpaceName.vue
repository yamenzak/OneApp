<template>
  <!--
    An app's name, written the way the family is written.

    Every app of ours is `One` and a word — OneMail, OneStorage, OneCalendar —
    and the prefix is the part that is the same on all of them. Said at full
    strength it is four letters of noise repeated down a column; said quietly it
    does what the twin cuts scored through the artwork used to do and could not
    do at icon size, which is to say "these belong together" without getting in
    the way of which one you are looking at.

    So the signature moved from the drawing to the word.

    Two names are not ours to style: a space a customer named, and an assistant
    a workspace named. Those are said whole, at full strength, because a name
    somebody chose is not a variation on ours.
  -->
  <!-- No overflow rule of its own: the trigger wants one line truncated and a
       tile wants two lines clamped, and that is the caller's business. -->
  <span>
    <template v-if="split">
      <span class="text-ink-gray-4">{{ split[0] }}</span
      ><span class="text-ink-gray-7">{{ split[1] }}</span>
    </template>
    <span v-else class="text-ink-gray-7">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { MARKS } from '@/shared/lib/brand/marks'

const props = defineProps({
  /** The mark this thing wears, if it wears one of ours. */
  brand: { type: String, default: '' },
  /** What to say when the product name is not what should be said. */
  label: { type: String, default: '' },
  /** True where the name on screen is somebody else's choice, not ours. */
  renamed: { type: Boolean, default: false },
})

const PREFIX = 'One'

// The mark's own name, which is the product's — `nav.js` and a manifest both
// carry a *label*, and a label is what a thing does rather than what it is
// called. Only where the name is ours to write.
const split = computed(() => {
  if (props.renamed) return null
  const name = MARKS[props.brand]?.name || ''
  return name.startsWith(PREFIX) && name.length > PREFIX.length
    ? [PREFIX, name.slice(PREFIX.length)]
    : null
})
</script>

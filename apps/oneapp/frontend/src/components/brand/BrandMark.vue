<template>
  <!--
    One app's mark, inline.

    Inline and not an `<img src="/assets/…/onesheet.svg">` for two reasons: it
    scales with the type around it, and it can be handed a `class`. The
    standalone files `gen_brand.py` also writes are for the surfaces that are
    not this app — a favicon, an email, a print.

    The mark is drawn in its own colours and does not follow the theme. That is
    deliberate and is what makes an app recognisable at 20px in a rail: an icon
    that took the workspace's accent would be the workspace's icon, not the
    app's. The white inside each mark is structural — a pallet, a chip, a page
    — and reads on both grounds because it sits inside a coloured shape rather
    than against the canvas.
  -->
  <svg
    viewBox="0 0 100 100"
    :class="$attrs.class"
    :data-slot="`brand-${name}`"
    role="img"
    :aria-label="label"
    v-html="drawn"
  />
</template>

<script setup>
import { computed } from 'vue'
import { MARKS, UNIQUE } from '@/lib/brand/marks'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  /** A key of `MARKS` — `onesheet`, `onecrm`, or `one` for the platform. */
  name: { type: String, required: true },
})

const mark = computed(() => MARKS[props.name] || null)

const label = computed(() => mark.value?.name || props.name)

/**
 * A number nothing else on the page will have.
 *
 * The gradient and mask ids inside a mark are global to the document, so two
 * copies of one mark would be two elements sharing an id — and a `v-if` that
 * unmounts either takes the gradient the other one points at with it, which
 * renders as a shape that suddenly loses its fill. Computed rather than
 * generated once at module load, so a component reused across two marks gets
 * two sets.
 */
let seq = 0
const drawn = computed(() => {
  if (!mark.value) return ''
  seq += 1
  return mark.value.body.replaceAll(UNIQUE, `-${props.name}-${seq}`)
})
</script>

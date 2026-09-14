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
    app's. The white inside each mark is light rather than paper — a highlight
    at 12% over obsidian, the hot centre of the beacon, the lit edge of the
    chassis — and every one of them sits inside a coloured object, so none of
    them needs the canvas to be any particular colour.
  -->
  <!--
    `v-html`, and the rule that objects to it is switched off for this one
    element. What goes in is not a string from anywhere: it is a mark out of
    `lib/brand/marks.js`, which `scripts/gen_brand.py` writes from a page in
    this repository. Nothing a customer or a request can reach touches it, and
    an SVG cannot be assembled from components without transcribing sixteen
    marks into Vue templates by hand.
  -->
  <!-- eslint-disable vue/no-v-html -->
  <svg
    :viewBox="box"
    :class="$attrs.class"
    :data-slot="`brand-${name}`"
    role="img"
    :aria-label="label"
    v-html="drawn"
  />
  <!-- eslint-enable vue/no-v-html -->
</template>

<script setup>
import { computed } from 'vue'
import { MARKS, UNIQUE } from '@/shared/lib/brand/marks'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  /** A key of `MARKS` — `onesheet`, `onecrm`, or `one` for the platform. */
  name: { type: String, required: true },
})

const mark = computed(() => MARKS[props.name] || null)

const label = computed(() => mark.value?.name || props.name)

// The mark's own, not a constant: the set is drawn on a 192 grid and the one
// before it was drawn on 100, and a mark rendered in the wrong box is a quarter
// of a mark in the corner of an empty square. A name this build does not have
// draws nothing, so the box it gets does not matter — it just has to be valid.
const box = computed(() => mark.value?.box || '0 0 192 192')

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

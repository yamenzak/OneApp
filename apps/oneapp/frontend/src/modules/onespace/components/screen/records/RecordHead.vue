<!--
  The band across the top of a bespoke record view: who this is, where it
  stands, and the one number it is judged on.

  Seven of the eight drew it, and drew it character for character the same —
  the same eleven utilities on the band, the same `flex min-w-0 flex-1` column,
  the same eyebrow, the same title row with the badge wrapping beside it. What
  differed was three things, and all three are slots or props here: what sits
  *before* the column (a portrait, an initial), what sits *under* the title
  (a date, a run of chips, a pay range), and what sits at the trailing end.

  **Every `data-slot` is passed in.** They are not derived from `name` and they
  are not tidied: `absence-kind`, `payslip-period` and `boarding-eyebrow` are
  the same element under three words, because the word says what that view's
  eyebrow *is*. Browser specs select on them, so they are a contract — and a
  refactor that renames a contract to make a component neater has moved the
  cost onto whoever next runs the suite.

  The `badges` slot is a second chip beside the state, and one view uses it:
  a person's *presence* sits next to their employment status because Active and
  In are different sentences, and a page showing only the second would have
  nothing to say about somebody who left in March.

  `align` is the one real variation in the band itself. `openings` stacks two
  sentences and a pay range in its column, so its trailing block has to sit at
  the top rather than in the middle of a column three lines taller than it.

  `PlaceRecord` deliberately does not use this. It has no eyebrow, no badge and
  no trailing number — it is a rule and two settings — and dressing it in a
  band it does not want is how a shared component starts growing flags.
-->
<template>
  <div
    class="flex flex-col gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:flex-row md:gap-6 md:px-6"
    :class="ALIGN[align] || ALIGN.center"
  >
    <slot name="portrait" />

    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <p
        v-if="eyebrow"
        :data-slot="eyebrowSlot"
        class="truncate text-sm text-ink-muted"
      >{{ eyebrow }}</p>

      <div class="flex min-w-0 flex-wrap items-center gap-2">
        <h2
          :data-slot="titleSlot"
          class="min-w-0 truncate text-xl-semibold text-ink-primary"
        >{{ title }}</h2>
        <StateBadge v-if="badge" :label="badge" :states="states" />
        <slot name="badges" />
      </div>

      <slot />
    </div>

    <slot name="aside" />
  </div>
</template>

<script setup>
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'

/**
 * Where the band's children sit against each other.
 *
 * A map rather than a ternary in the `:class`, because a comparison there puts
 * a bare word next to a class name and nothing downstream can tell them apart
 * — `tests/test_design_tokens.py` read `start` as a class and asked why it
 * emitted no CSS, which is the guard being right.
 */
const ALIGN = {
  start: 'md:items-start',
  center: 'md:items-center',
}

defineProps({
  /** The line above the title, and the slot the specs know it by. */
  eyebrow: { type: String, default: '' },
  eyebrowSlot: { type: String, default: '' },
  title: { type: String, default: '' },
  titleSlot: { type: String, required: true },
  badge: { type: String, default: '' },
  states: { type: Object, default: () => ({}) },
  /** `start` for a column tall enough that centring the aside looks adrift. */
  align: { type: String, default: 'center' },
})
</script>

<template>
  <!--
    A handful of facts about a record, in a quiet divided row under its band.

    Four at most, which is `showcase.FACTS`, and they wrap rather than scroll:
    a phone gets two rows of two. Four columns of label-over-value floating in
    space read as a table that lost its rules — the dividers are what make them
    four *facts* rather than eight stacked words.

    Extracted at its second caller: the person page and the candidate page.
    Both had the same row under the same kind of band, and the second one
    copying it is how `docs/UNIFICATION.md` F1 says this repository keeps going
    wrong.
  -->
  <dl
    v-if="facts.length"
    :data-slot="slotName"
    class="grid grid-cols-2 border-b border-outline-gray-2"
    :class="COLUMNS[facts.length] || COLUMNS[4]"
  >
    <div
      v-for="(fact, at) in facts"
      :key="fact.field"
      class="flex min-w-0 flex-col gap-1 border-outline-gray-2 px-4 py-3 md:px-6"
      :class="at === facts.length - 1 ? '' : 'border-e'"
    >
      <dt class="flex min-w-0 items-center gap-1.5 text-xs text-ink-muted">
        <Icon v-if="fact.icon" :name="fact.icon" class="size-3.5 shrink-0" />
        <span class="truncate">{{ fact.label }}</span>
      </dt>
      <!--
        Stronger than the label and quieter where there is nothing: an em dash
        in the same weight as a real value makes a row of four look like a row
        of four answers, one of which is a dash.
      -->
      <dd
        class="truncate text-base-medium"
        :class="fact.text ? 'text-ink-primary' : 'text-ink-gray-4'"
        :title="fact.text"
      >{{ fact.text || '—' }}</dd>
    </div>
  </dl>
</template>

<script setup>
import { Icon } from '@/ui'

// The row follows the count. Four columns for three facts leaves an empty cell
// with a rule down one side of it, which reads as a fact whose label failed to
// load rather than as a fact nobody declared. Named classes rather than an
// arbitrary `grid-cols-[…]`, which is the rail against a value appearing in
// more than one file.
const COLUMNS = {
  1: 'md:grid-cols-1',
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-3',
  4: 'md:grid-cols-4',
}

defineProps({
  /** `[{field, label, text, icon}]`, already resolved to what is printed. */
  facts: { type: Array, default: () => [] },
  /** What a test looks this row up by. Each page names its own — `slot` is a
   *  reserved attribute name, so this follows `AvatarStack`'s `slot-name`. */
  slotName: { type: String, default: 'record-facts' },
})
</script>

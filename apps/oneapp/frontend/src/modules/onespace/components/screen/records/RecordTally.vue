<!--
  One number, with the word for what it is under it.

  The right-hand end of a record's band: how many days are being asked for,
  what lands in the account, how long somebody was here. Four of the views drew
  it and drew it identically — `text-2xl-semibold tabular-nums` over
  `text-xs text-ink-muted`, right-aligned above the fold and stacked below it.

  `tabular-nums` is the part worth keeping in one place. Proportional digits
  make a column of figures ripple, and this is the number a page is a judgement
  about.

  The caption is a slot as well as a prop, because two of the four draw a
  comparison rather than a word — "of 8 hours", with the standard in it.
-->
<template>
  <div
    :data-slot="name"
    class="flex shrink-0 flex-col gap-0.5 md:items-end"
  >
    <p class="text-2xl-semibold tabular-nums text-ink-primary">{{ value }}</p>
    <p class="text-xs text-ink-muted">
      <slot name="caption">{{ caption }}</slot>
    </p>
  </div>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  value: { type: [String, Number], default: '' },
  caption: { type: String, default: '' },
})
</script>

<!--
  The outer shell every bespoke record view is drawn in.

  `RecordView` gives a record view a column with its own padding, and every one
  of these wants to bleed to the edge of it and sit above the tab strip. So
  they all opened with the same four negative-margin utilities and the same
  `data-slot` convention, eight times, and the day the strip moves is the day
  somebody edits eight files and misses one.

  `name` is the view's own word — `absence`, `payslip` — and the slot is
  `<name>-record`, which is what the browser specs select on. Passed rather
  than derived from the component, because a spec naming a DOM attribute is a
  contract and a filename is not.
-->
<template>
  <section :data-slot="`${name}-record`" class="-mx-4 -mt-4 mb-4 flex flex-col">
    <slot />
  </section>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
})
</script>

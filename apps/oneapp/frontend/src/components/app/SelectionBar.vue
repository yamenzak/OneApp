<template>
  <!--
    What a selection is for, floating over the list rather than pushing it down.

    Frappe CRM puts this bar at the bottom of the screen instead of above the
    rows, and it is the better place: ticking a box near the end of a long list
    used to fire an action bar into a part of the page nobody was looking at.
    Sticky rather than fixed, so it clears the phone's navigation bar without
    knowing how tall that is — it pins to the bottom of whatever is scrolling,
    and on a phone that container stops above the nav.
  -->
  <div class="sticky bottom-4 z-20 mt-3 flex justify-center px-2">
    <div :class="BAR">
      <span class="whitespace-nowrap text-p-base text-ink-gray-8"> {{ count }} selected </span>

      <div class="ms-2 flex items-center gap-1 border-s border-outline-gray-2 ps-3">
        <slot />
        <Button v-if="count < total" variant="ghost" label="Select all" @click="emit('all')" />
        <Button
          icon="lucide-x"
          variant="ghost"
          label="Clear the selection"
          @click="emit('clear')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { Button } from '@/ui'

defineProps({
  count: { type: Number, required: true },
  total: { type: Number, default: 0 },
})
const emit = defineEmits(['clear', 'all'])

// The same shape frappe-ui's own select banner draws — an elevated pill, not a
// panel — so it reads as floating over the list rather than as another band in
// it. `rounded-6` is the panel radius; see `docs/APPS.md` on the radius scale.
//
// `surface-elevation-2` rather than the `surface-base` frappe-ui's own banner
// uses: a shadow is invisible against a dark background, so in dark mode the
// thing that says "this floats" is the lighter surface, not the shadow.
const BAR = 'flex items-center gap-1 rounded-6 bg-surface-elevation-2 px-3 py-1.5 shadow-2xl'
</script>

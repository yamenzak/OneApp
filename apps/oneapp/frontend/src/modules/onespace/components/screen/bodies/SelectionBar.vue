<template>
  <!--
    What a selection is for, floating over the list rather than pushing it down.

    Frappe CRM puts this bar at the bottom of the screen instead of above the
    rows, and it is the better place: ticking a box near the end of a long list
    used to fire an action bar into a part of the page nobody was looking at.

    Absolute within the grid pane rather than fixed to the window, so it floats
    over the rows and clears the footer without knowing anything about the
    shell around it — on a phone that pane already stops above the navigation
    bar. The wrapper does not take pointer events, or an invisible full-width
    strip would eat clicks on the rows beneath it.
  -->
  <div class="pointer-events-none z-20 flex justify-center px-2" :class="WHERE[anchor]">
    <div data-slot="selection-bar" class="pointer-events-auto" :class="BAR">
      <span class="whitespace-nowrap text-base text-ink-primary">{{ __('{0} selected', [count]) }}</span>

      <div class="ms-2 flex items-center gap-1 border-s border-outline-gray-2 ps-3">
        <slot />
        <Button v-if="count < total" variant="ghost" :label="__('Select all')" @click="emit('all')" />
        <Button
          icon="lucide-x"
          variant="ghost"
          :label="__('Clear the selection')"
          :tooltip="__('Clear the selection')"
          @click="emit('clear')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { Button } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  count: { type: Number, required: true },
  total: { type: Number, default: 0 },
  /**
   * What the bar floats over: the pane it was rendered into, or the window.
   *
   * `pane` is the default and the better answer where there is a pane to
   * float over — a record list, a mailbox column — because the bar then sits
   * over the rows it is about rather than over the middle of the screen.
   *
   * `screen` is for a list that *is* the scroller. The Drive's rows scroll in
   * the same element the bar would be absolute inside, so a pane-anchored bar
   * would scroll away with them; fixed to the window is what the Drive's own
   * hand-rolled bar did before there was one component.
   */
  anchor: { type: String, default: 'pane', validator: (v) => ['pane', 'screen'].includes(v) },
})
const emit = defineEmits(['clear', 'all'])

// `bottom-24` on a phone clears the navigation bar; the pane-anchored one does
// not have to, because that pane already stops above it.
const WHERE = {
  pane: 'absolute inset-x-0 bottom-16',
  screen: 'fixed inset-x-0 bottom-24 md:bottom-6',
}

// The same shape frappe-ui's own select banner draws — an elevated pill, not a
// panel — so it reads as floating over the list rather than as another band in
// it. `rounded-6` is the panel radius; see `docs/ONESPACE.md` on the radius scale.
//
// `surface-elevation-2` rather than the `surface-base` frappe-ui's own banner
// uses: a shadow is invisible against a dark background, so in dark mode the
// thing that says "this floats" is the lighter surface, not the shadow.
//
// `max-w-full` and wrapping because a phone is 390px and the Drive's bin puts
// two verbs and a count on it: without them the buttons ran off the edge.
const BAR = 'flex max-w-full flex-wrap items-center justify-center gap-1 rounded-6 bg-surface-elevation-2 px-3 py-1.5 shadow-over'
</script>

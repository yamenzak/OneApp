<template>
  <!--
    A row of people, overlapping, with a count for the ones that did not fit.

    The desk's own treatment and the one every product with assignment uses,
    for a reason worth stating: a list of names is as wide as the names, and
    the thing a reader actually asks of it — "is anybody on this, and is it
    me" — is answered by three faces in the width of one.

    Overlap by a negative margin rather than by absolute positioning, so the
    stack is still a flex row: it wraps into whatever space it is given.

    The gap between two faces is drawn as a padded background of the surface
    behind them rather than as a ring. `ring-*` takes a colour, and the theme's
    colours are background, text and outline — `ring-surface-white` is not a
    token and emits no CSS at all, which is a stack of faces touching.
  -->
  <div class="flex items-center">
    <Tooltip v-for="person in shown" :key="person.value" :text="person.label">
      <span
        :data-slot="slotName"
        class="-mr-1.5 inline-flex rounded-full bg-surface-base p-0.5 last:mr-0"
      >
        <Avatar :image="person.image" :label="person.label" shape="circle" :size="size" />
      </span>
    </Tooltip>

    <Tooltip v-if="overflow.length" :text="overflow.map((one) => one.label).join(', ')">
      <span
        class="ml-1.5 flex items-center rounded-full bg-surface-gray-3 px-1.5 text-p-xs tabular-nums text-ink-gray-6"
      >+{{ overflow.length }}</span>
    </Tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar, Tooltip } from '@/ui'

const props = defineProps({
  /** `[{ value, label, image }]` — the shape every identity here is drawn from. */
  people: { type: Array, default: () => [] },
  /** How many faces before the rest become a count. */
  limit: { type: Number, default: 3 },
  size: { type: String, default: 'sm' },
  /** What each face is called, for a test to point at. */
  slotName: { type: String, default: 'avatar' },
})

const shown = computed(() => props.people.slice(0, props.limit))
const overflow = computed(() => props.people.slice(props.limit))
</script>

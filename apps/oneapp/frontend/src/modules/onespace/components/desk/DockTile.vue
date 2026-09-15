<template>
  <!--
    One app in the dock: its mark, and whether you are in it.

    Three shapes rather than one, because an app is reached three ways and the
    difference has to be in the markup rather than in a click handler. A window
    presses. A page is a link — so middle-click opens a tab and hover shows the
    address, which a button can do neither of. An app this workspace has not got
    is neither: it is a plain element with the reason on it, because a disabled
    link is a link that refuses and `docs/UNIFICATION.md` F1 says the surface
    renders what the source declared, greyed and with the reason, rather than
    letting somebody find out by pressing.

    **Lit, not filled.** What marks the current app is a chip behind the mark —
    the same `surface-elevation-3` the rail's open screen uses — plus a short
    line under it. The line is what survives a mark that is already a bright
    square: a fill behind something with its own colours is a second colour
    fighting the first, and the dock is the one row in the product that is all
    marks.
  -->
  <component
    :is="app.act ? 'button' : app.to ? RouterLink : 'div'"
    :to="app.to"
    :type="app.act ? 'button' : undefined"
    :title="app.why || app.said || ''"
    :aria-label="app.label"
    :aria-current="app.active && app.to ? 'page' : undefined"
    :aria-disabled="app.to || app.act ? undefined : 'true'"
    :data-slot="app.to || app.act ? 'dock-tile' : 'dock-tile-off'"
    :data-app="app.key"
    :data-open="app.active ? 'yes' : 'no'"
    class="relative flex size-9 shrink-0 items-center justify-center rounded-4"
    :class="[
      app.to || app.act ? HOVER : 'cursor-default',
      app.active ? 'bg-surface-elevation-3' : '',
    ]"
    @click="app.act?.()"
  >
    <!--
      Dimmed rather than greyed, the same as the board's: a mark stripped of
      its colour is a different drawing, and a row of grey squircles reads as
      broken rather than as absent.
    -->
    <SpaceFace
      :space="{ label: app.label, brand: app.brand }"
      size="lg"
      decorative
      class="size-6"
      :class="app.to || app.act ? '' : 'opacity-40'"
    />

    <!-- What is waiting for you, on the app it is waiting in. -->
    <Badge
      v-if="app.count"
      theme="blue"
      :label="String(app.count > 99 ? '99+' : app.count)"
      class="pointer-events-none absolute -end-1 -top-1 scale-90"
    />

    <!-- Open, and under it, which is where every dock in the world puts it. -->
    <span
      v-if="app.active"
      class="pointer-events-none absolute bottom-0.5 h-0.5 w-3 rounded-full bg-ink-primary"
    />
  </component>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { Badge } from '@/ui'
import SpaceFace from '@/shared/components/brand/SpaceFace.vue'
import { HOVER } from '@/shared/lib/rowstate'

defineProps({
  /**
   * One entry from `useApps().dock`: the catalogue's own fields, plus
   * `active`, `count`, and either `to` (a page), `act` (a window) or neither
   * (not here, and `why` says so).
   */
  app: { type: Object, required: true },
})
</script>

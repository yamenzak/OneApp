<template>
  <!--
    One destination in the column's foot: Mail, Files, the calendar.

    None of them is inside a space — the addresses somebody holds do not change
    when they switch space, and neither does the workspace's file table — so
    none belongs in any space's navigation. They sit above the account and the
    notification bell, which are the last two things in the column everywhere in
    this product.

    One component for all of them, drawn from `useNav().surfaces`, for the
    reason that module exists: one list rendered twice, not two lists. Written
    as separate components they drifted immediately — one of them had a row in
    the phone's More sheet and the other did not.

    The badge is Mail's and would be wrong on Files. A count of files is not
    news: nothing there is waiting for you, which is the difference between a
    place you keep things and a place things arrive.

    One surface does not navigate. The assistant is a *panel* over whatever you
    are looking at, so its row toggles rather than goes — going would be leaving
    the thing you wanted to ask about. `surface.act` is how an entry says so.
  -->
  <component :is="surface.act ? 'div' : RouterLink" :to="surface.to" class="relative">
    <!--
      The lucide outline, not the app's own mark, even though these have one.

      This row is four things side by side at 20px, and a mark is a filled
      gradient square: four of them in a line read as a toolbar of stickers
      while everything else in the column is a line drawing. The marks are how
      you tell one app from another when you are *choosing* — which is the
      switcher, the launcher and the marketplace, and is where they are drawn.
      Here you are not choosing between apps, you are reaching for one.
    -->
    <Button
      variant="ghost"
      :icon="surface.icon"
      :label="surface.label"
      :tooltip="surface.label"
      :data-slot="`${surface.key}-link`"
      @click="surface.act?.()"
    />
    <Badge
      v-if="surface.count"
      theme="blue"
      :label="String(surface.count > 99 ? '99+' : surface.count)"
      class="pointer-events-none absolute -end-1 -top-1"
    />
  </component>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { Badge, Button } from '@/ui'

defineProps({
  /**
   * One entry from `useNav().surfaces`: key, label, icon, to, a count, and
   * `brand` where the surface is one of our own apps.
   */
  surface: { type: Object, required: true },
})
</script>

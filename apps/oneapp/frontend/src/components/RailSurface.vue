<template>
  <!--
    One destination in the rail's footer: Mail, Files.

    Both are surfaces that are not inside a space — the addresses somebody holds
    do not change when they switch space, and neither does the workspace's file
    table — so neither belongs in any space's navigation. They sit above the
    notification bell, which is above the account, which is the last thing in
    the rail everywhere in this product.

    One component for both, drawn from `useNav().surfaces`, for the reason that
    module exists: two renderings of one list, not two lists. Written as two
    components they drifted immediately — one of them had a row in the phone's
    More sheet and the other did not.

    The badge is Mail's and would be wrong on Files. A count of files is not
    news: nothing there is waiting for you, which is the difference between a
    place you keep things and a place things arrive.
  -->
  <RouterLink :to="surface.to" class="relative">
    <Button
      variant="ghost"
      :icon="surface.icon"
      :label="surface.label"
      :tooltip="surface.label"
      :data-slot="`${surface.key}-link`"
    />
    <Badge
      v-if="surface.count"
      theme="blue"
      :label="String(surface.count > 99 ? '99+' : surface.count)"
      class="pointer-events-none absolute -right-1 -top-1"
    />
  </RouterLink>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { Badge, Button } from '@/ui'

defineProps({
  /** One entry from `useNav().surfaces`: key, label, icon, to, and a count. */
  surface: { type: Object, required: true },
})
</script>

<template>
  <!--
    The foot of whichever column is showing, and what is left of it.

    It held three things: a row of app shortcuts, you, and the bell. All three
    were in the wrong place for the same reason — they are about the workspace
    and this is the foot of a column about one surface, so they folded to 3rem
    with it, moved when the route changed which sidebar it drew, and sat under
    whichever navigation happened to be above them. They are in the dock now
    (`components/desk/Dock.vue`), which is a row of the window's own width.

    What stays is the quota meter, which is the one thing down here that is not
    a way to somewhere else: it is a number about this workspace, and the
    reason it is at the foot of every column rather than of one is that it
    decides whether an upload is refused — so it has to be visible on the
    screen you upload from.
  -->
  <div v-if="!collapsed" class="mt-auto shrink-0 p-2">
    <!-- A meter is a number and a bar, and neither survives 3rem of width, so
         a folded column simply has no foot. -->
    <QuotaMeter class="px-1" />
  </div>
</template>

<script setup>
import QuotaMeter from '@/modules/onespace/components/QuotaMeter.vue'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'

const { collapsed } = useSidebar()
</script>

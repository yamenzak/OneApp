<template>
  <!--
    The row along the bottom, and the second thing in this product that has the
    standing of the bar along the top.

    What it replaces is two things that were solving the same problem badly.
    The sidebar's foot held a row of four glyphs — Mail, the calendar, Files,
    the assistant — which was a row of shortcuts inside a column of navigation:
    it scrolled with nothing, it folded to 3rem with the column, and it was
    under whichever sidebar the route happened to draw. And the assistant had a
    64px mark fixed in the opposite corner, because *it* had to be reachable
    from anywhere and a folded rail is not anywhere. Two permanent marks in two
    corners meaning nearly the same thing.

    So: one row, under the page. **Under the page and not the whole window**,
    which was the first try: the sidebar keeps its own foot — you and the bell,
    which are not places you go — and a dock spanning the sidebar too put two
    stacks of chrome in one corner and made this read as a second thing the
    navigation did.

    **The two ends answer different questions.** Everything at the start is
    somewhere to go or something to open. Everything at the end is what is true
    right now and opens nothing: the clock today, the weather after it.

    **Marks and not glyphs**, which is the one place this disagrees with the
    row it replaces. That row drew lucide outlines and its reason was good —
    four filled gradient squircles in a 20px line read as stickers in a column
    of line drawings. A dock is not a column of line drawings. It is the place
    you *choose* an app, which is the switcher's argument for marks, and at
    24px in a row of its own the set reads as a set.

    **What is not here.** The spaces: the switcher is where you change where
    you are, and the dock is what you open while you are there. The board's
    other twenty: a dock is the apps, not the catalogue, and the corner already
    answers "is there a OneTask".

    Desktop only. `docs/DESKTOP.md` stage 6 is where a phone gets this, and the
    answer there is the row the foot already draws.
  -->
  <footer
    data-slot="dock"
    class="relative z-10 hidden h-12 shrink-0 items-center gap-1 px-2 md:flex"
  >
    <!--
      The apps, at the start rather than centred.

      A centred dock is macOS's and it costs the one thing this row is for:
      with a window filling the desk the tiles have to be somewhere the eye can
      go without reading, and "the corner" is a place where "the middle of a row
      whose length changes with the workspace" is not.
    -->
    <div class="flex items-center gap-0.5" data-slot="dock-apps">
      <DockTile v-for="app in dock" :key="app.key" :app="app" />
    </div>

    <!--
      What is open and is not one of them.

      Empty today: the assistant is the only window there is and it has a tile
      already. Stage 3's picture-in-picture list is the first thing that will
      land here — a window with no app behind it still has to be somewhere you
      can get back to it from.
    -->
    <template v-if="loose.length">
      <div class="mx-1 h-5 w-px shrink-0 bg-surface-gray-4" />
      <div class="flex items-center gap-0.5" data-slot="dock-windows">
        <Button
          v-for="one in loose"
          :key="one.id"
          variant="ghost"
          :icon="one.icon || 'lucide-app-window'"
          :label="one.label"
          :tooltip="one.label"
          :class="shown(one.id) ? '!bg-surface-elevation-3' : ''"
          @click="press(one.id)"
        />
      </div>
    </template>

    <div class="flex-1" />

    <!--
      The shelf: what is true right now. Nothing here goes anywhere, which is
      what makes it the other end of the row rather than more of the same.
    -->
    <div class="flex shrink-0 items-center gap-3 pe-1" data-slot="dock-shelf">
      <DockClock />
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from '@/ui'
import DockClock from '@/modules/onespace/components/desk/DockClock.vue'
import DockTile from '@/modules/onespace/components/desk/DockTile.vue'
import { desk, press, shown } from '@/modules/onespace/lib/desk/windows'
import { useApps } from '@/modules/onespace/lib/shell/apps'

const { dock } = useApps()

/** The windows no tile above already stands for. */
const known = computed(() => new Set(dock.value.map((one) => one.window).filter(Boolean)))
const loose = computed(() => desk.open.filter((one) => !known.value.has(one.id)))
</script>

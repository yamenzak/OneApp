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

    So: one row, the width of the window, outside every column. It is where the
    apps are.

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
      go without reading, and "the corner" is a place where "the middle of a
      row whose length changes with the workspace" is not.
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
      You, and what is waiting for you — the two rows that were under the
      surfaces in the column's foot and had the same problem they did. The foot
      keeps the quota meter, which is the one thing down there that is a number
      about this workspace rather than a way to somewhere else.
    -->
    <div class="flex shrink-0 items-center gap-1" data-slot="dock-you">
      <NotificationBell />
      <!-- Boxed, because `UserMenu`'s own root is a Dropdown carrying
           `w-full` — it was written for the foot of a column and would
           otherwise take the whole of a row that has one. -->
      <div class="w-11 shrink-0">
        <UserMenu
          :compact="true"
          :name="fullName"
          :email="email"
          :avatar="userImage"
          :extra="accountRows"
        />
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/ui'
import DockTile from '@/modules/onespace/components/desk/DockTile.vue'
import NotificationBell from '@/modules/onespace/components/notifications/NotificationBell.vue'
import UserMenu from '@/modules/onespace/components/UserMenu.vue'
import { desk, press, shown } from '@/modules/onespace/lib/desk/windows'
import { useApps } from '@/modules/onespace/lib/shell/apps'
import { fullName, email, userImage } from '@/modules/onespace/lib/shell/user'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()
const { dock } = useApps()

/** The windows no tile above already stands for. */
const known = computed(() => new Set(dock.value.map((one) => one.window).filter(Boolean)))
const loose = computed(() => desk.open.filter((one) => !known.value.has(one.id)))

// The two rows `UserMenu` does not carry itself — appearance and signing out
// are its own. Settings is one of them rather than a tile, because it is not a
// place: it opens over whatever you were looking at, which is what every other
// row in this menu does.
const accountRows = computed(() => [
  {
    label: __('Account'),
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
  {
    label: __('Settings'),
    icon: 'lucide-settings',
    onClick: () => openSettings(),
  },
])
</script>

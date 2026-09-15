<template>
  <!--
    OneCloud on the desk, and the three editors beside it — `docs/DESKTOP.md`
    stage 6.

    A file manager is the thing people keep open beside what they are doing,
    which is what a window is for. It was a route, so opening it replaced the
    space you were in: to look at one drawing you left the project it belonged
    to, and coming back was the back button and a re-read.

    The route stays as the maximised case, so a deep link still works and a
    person who wants the whole screen has it.

    **Four windows, one component.** A document is a `File` and a workbook is a
    `File`, so OneWriter is not a second application over a second store — it
    is this one landed on `place=documents`, with its own tile, its own colour
    and its own corner. `lib/window.js` holds the list and the argument.

    **Its own corner, and not a family's.** Record previews share one box
    because you only ever look at one; two folders open at once is the reason
    file managers have windows at all — dragging between them is the gesture —
    so these cascade instead. That also means no tabs inside: this product's
    tab bar is the dock, and it already draws a face per thing.

    The rail comes inside, in OneCloud. On the page the shell lends its sidebar
    slot; a window has no shell, so the column and the list are one row in here
    — which is what every file manager looks like anyway. An editor's window
    has none: there is one place in it, and a rail there would be a column of
    doors out of the room you just opened.
  -->
  <DeskWindow
    v-if="onDesk(app.id)"
    :id="app.id"
    :title="nameOf(app.brand)"
    :width="app.rail ? 1040 : 900"
    :height="680"
    :min-width="app.rail ? 560 : 460"
    :min-height="360"
    :tint="colourOf(app.brand)"
    @close="close(app.id)"
  >
    <template #title>
      <BrandMark :name="app.brand" class="size-4 shrink-0" />
      <SpaceName :brand="app.brand" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 overflow-hidden">
      <DriveSidebar
        v-if="app.rail"
        windowed
        :place="at.place"
        :folder="at.folder"
        @go="goTo($event, app.id)"
      />
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <Drive windowed :at="at" @go="goTo($event, app.id)" />
      </div>
    </div>
  </DeskWindow>
</template>

<script setup>
import { computed } from 'vue'

import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Drive from '@/modules/onestorage/pages/Drive.vue'
import DriveSidebar from '@/modules/onestorage/components/DriveSidebar.vue'
import { DRIVE, appAt, goTo, whereIs } from '@/modules/onestorage/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf, nameOf } from '@/shared/lib/brand/naming'

const props = defineProps({
  /** Which of the four this is — `lib/window.js`. */
  id: { type: String, default: DRIVE },
})

const app = computed(() => appAt(props.id) || appAt(DRIVE))
const at = computed(() => whereIs(props.id))
</script>

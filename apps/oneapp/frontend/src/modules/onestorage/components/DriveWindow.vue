<template>
  <!--
    OneCloud, on the desk — `docs/DESKTOP.md` stage 6.

    A file manager is the thing people keep open beside what they are doing,
    which is what a window is for. It was a route, so opening it replaced the
    space you were in: to look at one drawing you left the project it belonged
    to, and coming back was the back button and a re-read.

    The route stays as the maximised case, so a deep link still works and a
    person who wants the whole screen has it.

    **Its own corner, and not a family's.** Record previews share one box
    because you only ever look at one; two folders open at once is the reason
    file managers have windows at all — dragging between them is the gesture —
    so these cascade instead. That also means no tabs inside: this product's
    tab bar is the dock, and it already draws a face per thing.

    The rail comes inside. On the page the shell lends its sidebar slot; a
    window has no shell, so the column and the list are one row in here — which
    is what every file manager looks like anyway.
  -->
  <DeskWindow
    v-if="onDesk(DRIVE)"
    :id="DRIVE"
    :title="__('OneCloud')"
    :width="1040"
    :height="680"
    :min-width="560"
    :min-height="360"
    @close="close(DRIVE)"
  >
    <template #title>
      <BrandMark name="onestorage" class="size-4 shrink-0" />
      <SpaceName brand="onestorage" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 overflow-hidden">
      <DriveSidebar
        windowed
        :place="at.place"
        :folder="at.folder"
        @go="goTo"
      />
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <Drive windowed :at="at" @go="goTo" />
      </div>
    </div>
  </DeskWindow>
</template>

<script setup>
import { reactive } from 'vue'

import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Drive from '@/modules/onestorage/pages/Drive.vue'
import DriveSidebar from '@/modules/onestorage/components/DriveSidebar.vue'
import { DRIVE } from '@/modules/onestorage/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * Where the window is looking, which is not the address.
 *
 * `docs/DESKTOP.md`: position and size are remembered per app, *which* windows
 * are open is not — a pasted link opens the page, not somebody else's desk. A
 * folder somebody opened beside what they were doing is the same kind of fact,
 * so it lives here and the page underneath keeps its own.
 *
 * It survives folding, because the window does: this component is mounted for
 * the session and the window's own `v-show` is what hides it.
 */
const at = reactive({ place: 'home', folder: '' })

function goTo(where) {
  at.place = where.place || 'home'
  at.folder = where.folder || ''
}
</script>

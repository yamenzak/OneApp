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
    :tint="colourOf('onestorage')"
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
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Drive from '@/modules/onestorage/pages/Drive.vue'
import DriveSidebar from '@/modules/onestorage/components/DriveSidebar.vue'
import { DRIVE, at, goTo } from '@/modules/onestorage/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf } from '@/shared/lib/brand/naming'
import { __ } from '@/shared/lib/runtime/translate'
</script>

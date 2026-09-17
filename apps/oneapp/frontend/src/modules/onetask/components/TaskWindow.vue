<template>
  <!--
    OneTask on the desk — `docs/WORK.md` §12, and the shape the dock has been
    advertising since `docs/DESKTOP.md` stage 2.

    Narrow and tall, because it is a column of one-line things you keep beside
    what you are doing. Nothing of its own in the bar: the service's three
    controls are all inside it and a window with a name in its bar and a second
    row under it holding one button is the band OneCloud spent a stage
    removing.

    Pressing a row still takes the *page* to it, in OneProject, which is what
    a window beside your work is for: the glance is here and the whole record
    is where records live.
  -->
  <DeskWindow
    v-if="onDesk(TASKS)"
    :id="TASKS"
    :title="nameOf('onetask')"
    :width="400"
    :height="620"
    :min-width="320"
    :min-height="320"
    :tint="colourOf('onetask')"
    @close="close(TASKS)"
  >
    <template #title>
      <BrandMark name="onetask" class="size-4 shrink-0" />
      <SpaceName brand="onetask" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Tasks />
    </div>
  </DeskWindow>
</template>

<script setup>
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Tasks from '@/modules/onetask/pages/Tasks.vue'
import { TASKS } from '@/modules/onetask/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf, nameOf } from '@/shared/lib/brand/naming'
</script>

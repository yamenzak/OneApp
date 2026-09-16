<template>
  <!--
    The diary on the desk — `docs/DESKTOP.md` stage 6, with mail.

    The week is the thing you check *against* what you are doing: is Tuesday
    free, when is the site visit, does this delivery clash. As a route that
    meant leaving the quotation to find out and coming back to write the
    answer.

    Nothing of its own inside. The diary is one grid and one verb — its New
    event teleports into this bar, because a window with a name in its bar and
    a second row under it holding one button is the band OneCloud spent a stage
    removing. Everything else on the grid belongs to a record somewhere else,
    and pressing one still takes the page underneath to it: a window over a
    quotation, and the entry that opens the *next* quotation moves the page,
    not the window. That is what a diary beside your work is for.
  -->
  <DeskWindow
    v-if="onDesk(DIARY)"
    :id="DIARY"
    :title="nameOf('onecalendar')"
    :width="900"
    :height="640"
    :min-width="480"
    :min-height="360"
    :tint="colourOf('onecalendar')"
    @close="close(DIARY)"
  >
    <template #title>
      <BrandMark name="onecalendar" class="size-4 shrink-0" />
      <SpaceName brand="onecalendar" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <Diary />
    </div>
  </DeskWindow>
</template>

<script setup>
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Diary from '@/modules/onecalendar/pages/Diary.vue'
import { DIARY } from '@/modules/onecalendar/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf, nameOf } from '@/shared/lib/brand/naming'
</script>

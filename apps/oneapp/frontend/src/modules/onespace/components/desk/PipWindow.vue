<template>
  <!--
    The list you came from, in a window, while you read one of its rows.

    It draws no list of its own — `lib/desk/pip.js` says why at length, and
    the short version is that a copy of a list is not the list: the filters
    would be the ones last saved rather than the ones actually applied, and the
    scroll would start at the top. `ScreenHost` teleports its own list in here,
    which is the same component with the same rows and the same unsaved
    narrowing, and picking a row navigates the page underneath because that is
    what picking a row in that list has always done.

    Mounted always, hidden until it is opened, and that is not laziness: a
    `<Teleport to="#…">` resolves its target when it patches, so a target that
    appears in the same tick as the teleport that wants it is a target Vue
    warns about and then ignores. The div is here whether or not anybody is
    looking at it.

    Wider and shorter than the assistant. A list is rows across, not a column
    of prose: 720 is about eight columns of a person list before the names
    start truncating, which is the point at which the window stops being able
    to answer "which of these is the next one".
  -->
  <DeskWindow
    :id="PIP"
    :title="pip.label"
    :label="__('{0}, beside what you are reading', [pip.label])"
    :width="720"
    :height="480"
    :min-width="480"
    @close="closePip"
  >
    <div :id="BODY" class="flex min-h-0 flex-1 flex-col overflow-hidden" />
  </DeskWindow>
</template>

<script setup>
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import { BODY, PIP, closePip, pip } from '@/modules/onespace/lib/desk/pip'
import { __ } from '@/shared/lib/runtime/translate'
</script>

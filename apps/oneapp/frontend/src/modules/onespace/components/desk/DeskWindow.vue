<template>
  <!--
    One window, and the only one there is.

    The assistant had all of this and was the only thing that did: a panel
    fixed over the page, a header you drag it by, a grip you resize it with, a
    corner it remembers and a close button. It was right, and it was also the
    shape `docs/UNIFICATION.md` F1 names — an abstraction built for one caller
    and re-implemented by the second. `docs/DESKTOP.md` is about there being
    several, so this is the extraction rather than a rewrite: the arithmetic
    moved to `lib/desk/geometry.js` and the chrome moved here.

    **The header is the handle.** Dragging anywhere else means a window that
    moves when somebody tries to select a line to copy it, which is the
    commonest thing anybody does inside one.

    **The grip is the bottom end corner**, which is the one change from the
    assistant's own. Its grip was the leading *top* corner, because it was
    anchored bottom-end and never moved — dragging out from the top left grew
    it away from the corner the eye was on. A window with a title bar is not
    anchored anywhere, and every desk in the world resizes from the corner
    furthest from the bar.

    **Maximised is the desk, not the screen.** The margin stays, so a window
    filling the desk still reads as a window over a page. The page underneath
    is the thing you came back to.

    **Folded is not closed.** `v-show` and not `v-if`: a window put away from
    the dock keeps its conversation, its scroll and its place in the stack, and
    pressing the tile again gets back the thing you had rather than a new one.

    Desktop only, and deliberately: a phone has no pointer to drag with and no
    room to put two things side by side. `docs/DESKTOP.md` stage 6 is where a
    window becomes a sheet.
  -->
  <Panel
    v-show="shown(id)"
    ground="base"
    pad="none"
    elevation="floating"
    as="aside"
    class="fixed hidden flex-col overflow-hidden md:flex"
    :style="{
      insetInlineStart: `${box.x}px`,
      top: `${box.y}px`,
      width: `${box.w}px`,
      height: `${box.h}px`,
      zIndex: zOf(id),
    }"
    :aria-label="label || title"
    data-slot="desk-window"
    :data-window="id"
    :data-full="filling ? 'yes' : 'no'"
    @keydown.esc="emit('close')"
    @pointerdown="raise(id)"
  >
    <div
      class="flex shrink-0 cursor-grab flex-col gap-2 border-b border-outline-gray-1 px-3 py-2.5 active:cursor-grabbing"
      data-slot="window-handle"
      @pointerdown="lift"
      @dblclick="toggleFull"
    >
      <div class="flex items-center justify-between gap-2">
        <!-- What this window is. A slot, because a tenant's own title is
             usually a mark and a name rather than a string — and a window
             whose title were only ever text would make the assistant draw its
             face somewhere else. -->
        <div class="flex min-w-0 items-center gap-2">
          <slot name="title">
            <p class="truncate text-base font-medium text-ink-primary">{{ title }}</p>
          </slot>
        </div>

        <!-- `@pointerdown.stop`, or pressing one of these starts a drag that
             swallows the click. -->
        <div class="flex shrink-0 items-center gap-0.5" @pointerdown.stop>
          <slot name="controls" />
          <!-- Put away rather than shut. The dock's tile does the same thing
               and is where a window goes when it is folded, so this is the
               same gesture reachable from the window itself — which is where
               somebody who wants it out of the way is already looking. -->
          <Button
            variant="ghost"
            icon="lucide-minus"
            :label="__('Put {0} away', [label || title])"
            :tooltip="__('Put away')"
            data-slot="window-fold"
            @click="fold(id)"
          />
          <Button
            variant="ghost"
            :icon="filling ? 'lucide-minimize-2' : 'lucide-maximize-2'"
            :label="filling ? __('Shrink it back') : __('Fill the desk')"
            :tooltip="filling ? __('Shrink') : __('Fill the desk')"
            data-slot="window-full"
            @click="toggleFull"
          />
          <Button
            variant="ghost"
            icon="lucide-x"
            :label="__('Close {0}', [label || title])"
            :tooltip="__('Close')"
            data-slot="window-close"
            @click="emit('close')"
          />
        </div>
      </div>

      <!-- Anything the tenant wants under its own name and still inside the
           bar: the assistant's context chip is the first. -->
      <slot name="under" />
    </div>

    <slot />

    <!-- Nothing to grab while it fills the desk: dragging the corner of a
         maximised window is a gesture with no meaning, and a cursor that
         promises one is a cursor that lies. -->
    <div
      v-if="!filling"
      class="absolute bottom-0 end-0 z-10 size-3 cursor-nwse-resize"
      data-slot="window-resizer"
      @pointerdown.prevent="stretch"
    />
  </Panel>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { Button } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import { fold, raise, shown, zOf } from '@/modules/onespace/lib/desk/windows'
import {
  FLOOR, SIZE, WHERE, fit, full, grow, keep, keepFull, opened, room, wasFull,
} from '@/modules/onespace/lib/desk/geometry'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Which window this is. The part that narrows the remembered geometry, so
   *  two tenants do not fight over one corner. */
  id: { type: String, required: true },
  /** Its name, in the bar and in the accessible name. */
  title: { type: String, default: '' },
  /** Where the two differ — a tenant whose bar draws a mark and a chip still
   *  needs one sentence for a screen reader. */
  label: { type: String, default: '' },
  /** How big it opens, before anybody has dragged it. */
  width: { type: Number, default: 400 },
  height: { type: Number, default: 560 },
  /** And the smallest it may be, where a tenant needs more than the floor. */
  minWidth: { type: Number, default: FLOOR.w },
  minHeight: { type: Number, default: FLOOR.h },
})

const emit = defineEmits(['close'])

const floor = () => ({
  w: Math.max(FLOOR.w, props.minWidth),
  h: Math.max(FLOOR.h, props.minHeight),
})

const box = reactive(opened(props.id, { w: props.width, h: props.height }))
const filling = ref(wasFull(props.id))

/** What it goes back to when it stops filling the desk. Held rather than
 *  recomputed: the point of shrinking is to get the window you had. */
const before = reactive({ ...box })

function settle() {
  Object.assign(box, filling.value ? full() : fit(box, room(), floor()))
}

if (filling.value) settle()

function toggleFull() {
  if (filling.value) {
    filling.value = false
    Object.assign(box, fit(before, room(), floor()))
  } else {
    Object.assign(before, { ...box })
    filling.value = true
    Object.assign(box, full())
  }
  keepFull(props.id, filling.value)
}

/** A drag, of either kind: hold the numbers here and write once on release. */
function drag(move) {
  const stop = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    keep(props.id, box, WHERE)
    keep(props.id, box, SIZE)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

function lift(event) {
  // A window filling the desk has nowhere to be dragged to, and dragging it
  // anyway would leave it the size of the desk in the wrong place.
  if (filling.value) return
  const fromX = event.clientX - box.x
  const fromY = event.clientY - box.y
  drag((moved) => {
    box.x = moved.clientX - fromX
    box.y = moved.clientY - fromY
    settle()
  })
}

/**
 * The bottom end corner, which grows it away from the bar.
 *
 * Only the size moves: the corner under the pointer is the far one, so the
 * window's own origin stays where it is and the title bar does not slide about
 * while somebody is resizing.
 *
 * The origin is **held** rather than read back, and that is not tidiness. Read
 * back, this feeds on itself: dragging past the right edge makes the window
 * wider than the room, `settle` pulls the origin left to fit it, and the next
 * pointer event measures the width from the new origin — so it is wider again,
 * and the window walks across the screen while somebody holds still. Four
 * hundred pixels became nine hundred in one drag.
 */
function stretch() {
  const from = { x: box.x, y: box.y }
  drag((moved) => {
    Object.assign(box, grow(from, { x: moved.clientX, y: moved.clientY }, room(), floor()))
    settle()
  })
}

// A desk that got smaller must not leave a window off the edge of it.
onMounted(() => window.addEventListener('resize', settle))
onBeforeUnmount(() => window.removeEventListener('resize', settle))
</script>

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

    **Drawn in the desk's own layer**, which is an element appended to `body` —
    `lib/desk/windows.js` says why at length, and the short version is that a
    dialog portals itself to `body` and a window drawn inside the page loses to
    it whatever its z-index says.

    **On a phone it is a sheet**: the whole screen, no drag, no grip, no fill.
    A phone has no pointer to drag with and no room to put two things side by
    side, so the desk's arithmetic simply does not apply there — and a window
    that drew nothing at all would be worse than any of it. The drawer this
    replaced was a full-screen overlay on a phone and a peeked record has to
    stay reachable. `docs/DESKTOP.md` stage 6 is the real phone pass; this is
    the part of it that could not wait, because it is the difference between a
    surface and no surface.
  -->
  <Teleport :to="`#${LAYER}`">
  <Panel
    v-show="shown(id)"
    ground="base"
    pad="none"
    elevation="floating"
    as="aside"
    class="pointer-events-auto fixed flex flex-col overflow-hidden"
    :class="phone ? 'inset-0 !rounded-none !border-0' : ''"
    :style="phone
      ? { zIndex: zOf(id) }
      : {
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
    <!--
      The bar is chrome, so it is the colour chrome is.

      `surface-sidebar` is the shell's ground — what the rail, the top bar and
      the dock all sit on, and the one token in that frame a declared ground
      moves — and `surface-base` is the page lifted off it. A window is a small
      shell over that page, so its bar belongs to the first group and its body
      to the second. Drawn in the page's own colour it read as more page with a
      rule across it, which is the one thing a title bar must not look like: it
      is the part you grab.
    -->
    <div
      class="flex shrink-0 flex-col gap-2 border-b border-outline-gray-2 bg-surface-sidebar px-3 py-2.5"
      :class="phone ? '' : 'cursor-grab active:cursor-grabbing'"
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
          <!-- Neither means anything on a phone: there is nowhere to put a
               window away *to* — the dock is not drawn there — and it already
               fills the screen. -->
          <Button
            v-if="!phone"
            variant="ghost"
            icon="lucide-minus"
            :label="__('Put {0} away', [label || title])"
            :tooltip="__('Put away')"
            data-slot="window-fold"
            @click="fold(id)"
          />
          <Button
            v-if="!phone"
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
      v-if="!filling && !phone"
      class="absolute bottom-0 end-0 z-10 size-3 cursor-nwse-resize"
      data-slot="window-resizer"
      @pointerdown.prevent="stretch"
    />
  </Panel>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { Button } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import { LAYER, fold, mountLayer, raise, shown, zOf } from '@/modules/onespace/lib/desk/windows'
import {
  FLOOR, SIZE, WHERE, fit, full, grow, keep, keepFull, opened, room, wasFull,
} from '@/modules/onespace/lib/desk/geometry'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Which window this is: its place in the stack and its tile in the dock. */
  id: { type: String, required: true },
  /**
   * Whose corner it remembers, where that is not its own.
   *
   * One window per tenant was the whole of it until a record preview became
   * several — one per record, each with its own id so each gets its own tile
   * — and a corner per *record* is a window that opens somewhere new every
   * time you glance at a different client. They are the same window to the
   * person dragging it, so they share one memory and one box.
   */
  memory: { type: String, default: '' },
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

// Asked here rather than passed in, the same way `ObjectPane` asks: how a
// surface renders at a width is the surface's own business.
const phone = useIsMobile()

const floor = () => ({
  w: Math.max(FLOOR.w, props.minWidth),
  h: Math.max(FLOOR.h, props.minHeight),
})

// Before the teleport looks for it: a `<Teleport to="#…">` resolves its target
// when it patches, and a target that does not exist yet is one Vue warns about
// and then ignores.
mountLayer()

/** The key the corner is filed under — see `memory`. */
const corner = props.memory || props.id

const box = reactive(opened(corner, { w: props.width, h: props.height }))
const filling = ref(wasFull(corner))

/** What it goes back to when it stops filling the desk. Held rather than
 *  recomputed: the point of shrinking is to get the window you had. */
const before = reactive({ ...box })

function settle() {
  Object.assign(box, filling.value ? full() : fit(box, room(), floor()))
}

if (filling.value) settle()

function toggleFull() {
  // Already the whole screen, and `full()` measures a desk that has no dock
  // under it there.
  if (phone.value) return
  if (filling.value) {
    filling.value = false
    Object.assign(box, fit(before, room(), floor()))
  } else {
    Object.assign(before, { ...box })
    filling.value = true
    Object.assign(box, full())
  }
  keepFull(corner, filling.value)
}

/** A drag, of either kind: hold the numbers here and write once on release. */
function drag(move) {
  const stop = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    keep(corner, box, WHERE)
    keep(corner, box, SIZE)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
}

function lift(event) {
  // A window filling the desk has nowhere to be dragged to, and dragging it
  // anyway would leave it the size of the desk in the wrong place. A phone has
  // no pointer to drag with and the sheet is the screen.
  if (filling.value || phone.value) return
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

// A desk that got smaller must not leave a window off the edge of it. Harmless
// on a phone, where nothing reads `box`.
onMounted(() => window.addEventListener('resize', settle))
onBeforeUnmount(() => window.removeEventListener('resize', settle))
</script>

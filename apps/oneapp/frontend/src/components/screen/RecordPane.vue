<template>
  <!--
    An open record. Beside the list on a desktop, over it on a phone.

    Frappe CRM's shape, and it earns its place for a reason a dialog cannot:
    a record is a place you work *while* looking at the list — mark this one
    done, glance at the next, come back — and a modal takes the list away and
    the page out of the accessibility tree with it. A pane keeps both.

    On a phone there is no room to keep both, so it is a page: full width, its
    own header, and the way back where the way back goes.
  -->
  <div
    v-if="phone"
    data-slot="record-pane"
    class="fixed inset-x-0 bottom-0 top-0 z-20 flex flex-col bg-surface-base"
  >
    <slot name="body" :phone="true" />
  </div>

  <template v-else>
    <!--
      The handle. Its own element rather than a border, because a 1px target is
      a target nobody hits: this is 5px of grab area drawn as a 1px rule.
    -->
    <div
      data-slot="record-resizer"
      role="separator"
      aria-orientation="vertical"
      :aria-label="`Resize the record, currently ${Math.round(width)} pixels`"
      tabindex="0"
      class="w-1.5 shrink-0 cursor-col-resize touch-none select-none border-l transition-colors hover:border-outline-gray-3"
      :class="dragging ? 'border-outline-gray-3' : 'border-outline-gray-2'"
      @pointerdown="grab"
      @keydown="nudge"
      @dblclick="reset"
    />

    <div
      data-slot="record-pane"
      class="flex shrink-0 flex-col overflow-hidden"
      :style="{ width: `${width}px` }"
    >
      <slot name="body" :phone="false" />
    </div>
  </template>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useIsMobile } from '@/lib/screen'

const props = defineProps({
  /** How wide the pane may get, as a share of the window. */
  maxShare: { type: Number, default: 0.6 },
})

// Asked here rather than passed in: how a surface renders at a width is the
// surface's own business, and the screen host is not allowed to ask the
// viewport anything — see `test_the_screen_host_shows_the_same_columns_on_every_screen`.
const phone = useIsMobile()

// Narrow enough that a form is still readable, and no narrower: below this the
// labels wrap and the pane is a column of hyphens.
const MIN = 360
const DEFAULT = 480
const REMEMBERED = 'onespace.record-pane'

// Remembered per person, in this browser. Not on the server: how wide somebody
// likes a pane is a property of the screen they are sitting at, and syncing it
// would make a laptop and a monitor argue.
const stored = () => {
  try {
    return Number(window.localStorage.getItem(REMEMBERED)) || 0
  } catch {
    // A private window, or site data turned off. A default is a fine answer.
    return 0
  }
}

const width = ref(Math.max(MIN, stored() || DEFAULT))
const dragging = ref(false)

const ceiling = computed(() => Math.max(MIN, window.innerWidth * props.maxShare))

const put = (next) => {
  width.value = Math.min(Math.max(next, MIN), ceiling.value)
}

const remember = () => {
  try {
    window.localStorage.setItem(REMEMBERED, String(Math.round(width.value)))
  } catch {
    // Nothing to do about it, and nothing worth saying: the pane still works.
  }
}

let start = 0
let from = 0

const move = (event) => {
  // Dragging left widens: the handle is on the pane's left edge.
  put(from + (start - event.clientX))
}

const release = () => {
  dragging.value = false
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerup', release)
  remember()
}

const grab = (event) => {
  event.preventDefault()
  dragging.value = true
  start = event.clientX
  from = width.value
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', release)
}

// The same handle from the keyboard, because a drag is not something everybody
// can do. A separator with a tabindex and no keys is a promise the page does
// not keep.
const nudge = (event) => {
  const step = event.shiftKey ? 64 : 16
  if (event.key === 'ArrowLeft') put(width.value + step)
  else if (event.key === 'ArrowRight') put(width.value - step)
  else if (event.key !== 'Home') return
  else put(DEFAULT)
  event.preventDefault()
  remember()
}

const reset = () => {
  put(DEFAULT)
  remember()
}

// A window that shrank below what the pane was given leaves the list with no
// room at all, so the ceiling is applied again rather than only on drag.
const fit = () => put(width.value)
window.addEventListener('resize', fit)
onBeforeUnmount(() => {
  window.removeEventListener('resize', fit)
  release()
})

watch(phone, (yes) => {
  if (yes) release()
})
</script>

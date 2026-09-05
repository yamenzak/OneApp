<template>
  <!--
    A drag handle that sets one number.

    Its own element rather than a border, because a 1px target is a target
    nobody hits: this is 6px of grab area drawn as a 1px rule.

    Everything about resizing lives here — the floor and the ceiling, the
    keyboard, the width remembered per browser, the re-clamp when the window
    shrinks — so a second thing that resizes is a `<Resizer>` rather than a
    second copy of all of it. The pane was the first; the sidebar is the next.
  -->
  <div
    :data-slot="slotName"
    role="separator"
    aria-orientation="vertical"
    :aria-label="`Resize ${label}, currently ${Math.round(size)} pixels`"
    tabindex="0"
    class="w-1.5 shrink-0 cursor-col-resize touch-none select-none transition-colors"
    :class="[edge, dragging ? 'border-outline-gray-3' : IDLE]"
    @pointerdown="grab"
    @keydown="nudge"
    @dblclick="reset"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'

const props = defineProps({
  /** Narrowest it may get. Below this the thing being resized is unreadable. */
  min: { type: Number, required: true },
  /** What a double-click, and a browser with nothing remembered, gives. */
  defaultSize: { type: Number, required: true },
  /** Widest, absolute. Combined with `maxShare`; the smaller of the two wins. */
  max: { type: Number, default: Infinity },
  /**
   * Widest, as a share of the window. A pane may take six tenths of the screen
   * and no more — which is a rule about the *window*, so it is re-applied when
   * the window changes rather than only while dragging.
   */
  maxShare: { type: Number, default: 0 },
  /**
   * Which edge the handle is on, and so which way a drag grows the thing.
   * `left` is a pane on the right of the screen: dragging left widens it.
   */
  side: { type: String, default: 'left' },
  /** What the separator says it resizes, for a screen reader. */
  label: { type: String, default: 'this panel' },
  /**
   * A localStorage key, or empty for a size that lasts one visit.
   *
   * Per browser and never on the server: how wide somebody likes a pane is a
   * property of the screen they are sitting at, and syncing it would make a
   * laptop and a monitor argue.
   */
  remember: { type: String, default: '' },
  /** For a test to point at. */
  slotName: { type: String, default: 'resizer' },
})

const size = defineModel({ type: Number, required: true })

const dragging = defineModel('dragging', { type: Boolean, default: false })

// Computed rather than a ternary in the binding: `test_every_class_emits_css`
// reads the string literals out of a `:class` and checks each is a real
// utility, so `side === 'left' ? …` offered it `left` as a class name and it
// rightly said that emits no CSS.
const IDLE = 'border-outline-gray-2 hover:border-outline-gray-3'
const edge = computed(() => (props.side === 'left' ? 'border-l' : 'border-r'))

const ceiling = computed(() => {
  const share = props.maxShare ? window.innerWidth * props.maxShare : Infinity
  return Math.max(props.min, Math.min(props.max, share))
})

// Returns what it settled on rather than leaving the caller to read it back.
//
// `defineModel` is not a plain ref: its getter returns `props.modelValue`, so a
// read straight after a write is the *old* value until the parent re-renders.
// The first version of this stored `size.value` inside `keep()` immediately
// after `put()`, which wrote the width the pane had before the nudge — the
// handle moved, the pane resized, and a reload put it back where it started.
const put = (next) => {
  const settled = Math.min(Math.max(next, props.min), ceiling.value)
  size.value = settled
  return settled
}

const stored = () => {
  if (!props.remember) return 0
  try {
    return Number(window.localStorage.getItem(props.remember)) || 0
  } catch {
    // A private window, or site data turned off. A default is a fine answer.
    return 0
  }
}

const keep = (value) => {
  if (!props.remember) return
  try {
    window.localStorage.setItem(props.remember, String(Math.round(value)))
  } catch {
    // Nothing to do about it, and nothing worth saying: it still works.
  }
}

let start = 0
let from = 0
// Where it actually is, for the same reason `put` returns it: the model reads
// back one render behind.
let at = 0

const move = (event) => {
  const by = props.side === 'left' ? start - event.clientX : event.clientX - start
  at = put(from + by)
}

const release = () => {
  dragging.value = false
  window.removeEventListener('pointermove', move)
  window.removeEventListener('pointerup', release)
  keep(at)
}

const grab = (event) => {
  event.preventDefault()
  dragging.value = true
  start = event.clientX
  from = size.value
  at = size.value
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', release)
}

// The same handle from the keyboard, because a drag is not something everybody
// can do. A separator with a tabindex and no keys is a promise the page does
// not keep.
const nudge = (event) => {
  const step = event.shiftKey ? 64 : 16
  const grows = props.side === 'left' ? 'ArrowLeft' : 'ArrowRight'
  const shrinks = props.side === 'left' ? 'ArrowRight' : 'ArrowLeft'
  if (event.key === grows) at = put(size.value + step)
  else if (event.key === shrinks) at = put(size.value - step)
  else if (event.key === 'Home') at = put(props.defaultSize)
  else return
  event.preventDefault()
  keep(at)
}

const reset = () => {
  keep(put(props.defaultSize))
}

// A window that shrank below what was given leaves nothing beside it, so the
// ceiling is applied again rather than only on drag.
const fit = () => {
  at = put(size.value)
}

onMounted(() => {
  at = put(stored() || props.defaultSize)
  window.addEventListener('resize', fit)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', fit)
  release()
})

// Unmounted while dragging — the pane became a page under a phone's width —
// leaves two window listeners bound to a component that is gone.
watch(() => props.min, fit)
</script>

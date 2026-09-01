<template>
  <!--
    A bounded scroller that says where it ends.

    A list inside a menu or a panel is clipped by its container, and a row cut
    in half by a hard edge reads as a rendering fault rather than as "there is
    more below". A soft fade at whichever edge has content past it says the
    second thing.

    Not the wash the list used to have across its left and right edges. That
    one dimmed *data* — a column of values, greyed for no reason a reader could
    name — and it was rightly called childish. This fades three-quarters of an
    inch of empty container above and below a bounded panel, and it disappears
    the moment there is nothing past the edge, which is what makes it
    information rather than decoration.

    Measured with a `ResizeObserver` as well as on scroll: the content of a
    filtered list changes without anybody scrolling, and the first version of
    the list's own edges measured before layout and said nothing until
    something else moved.

    Sideways it draws a hairline rather than a wash — see `axis`.
  -->
  <div class="relative min-h-0" :class="sideways ? 'min-w-0' : ''">
    <div
      ref="scroller"
      class="h-full overscroll-contain"
      :class="sideways ? 'overflow-x-auto' : 'overflow-y-auto'"
      @scroll.passive="measure"
    >
      <slot />
    </div>

    <div v-if="before" :class="[EDGE, beforeEdge]" />
    <div v-if="after" :class="[EDGE, afterEdge]" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /**
   * Which way it scrolls, and so which edges say there is more.
   *
   * `y` fades: a bounded panel of rows ends in a soft edge and the fade is over
   * empty container, not over data. `x` draws a hairline instead — the same
   * answer the list came to. A wash down the side of a table dims the values in
   * the column under it to talk about scrolling, which is the "childish glow"
   * that came off the list; a rule is the honest version and it is what the
   * grid already uses.
   */
  axis: { type: String, default: 'y' },
})

const sideways = computed(() => props.axis === 'x')

const EDGE = 'pointer-events-none absolute z-10'

// From the surface behind it to nothing. `from-surface-base` and not a colour:
// the fade has to be the panel's own background or it is a grey band in dark
// mode.
const FADE = 'inset-x-0 h-6 from-surface-base to-transparent'
const RULE = 'inset-y-0 w-0 border-l border-outline-gray-2'

const beforeEdge = computed(() =>
  sideways.value ? `${RULE} left-0` : `${FADE} top-0 bg-gradient-to-b`,
)
const afterEdge = computed(() =>
  sideways.value ? `${RULE} right-0` : `${FADE} bottom-0 bg-gradient-to-t`,
)

const scroller = ref(null)
// Whether there is content past each edge. Both false on something that fits.
const before = ref(false)
const after = ref(false)

// A pixel of slack at each end. A scroller sitting exactly at its end can
// report a fractional difference on a display with a scale factor, and an edge
// that never quite goes away is worse than one that never appears.
const SLACK = 1

const measure = () => {
  const el = scroller.value
  if (!el) return
  const at = sideways.value ? el.scrollLeft : el.scrollTop
  const shown = sideways.value ? el.clientWidth : el.clientHeight
  const whole = sideways.value ? el.scrollWidth : el.scrollHeight
  before.value = at > SLACK
  after.value = at + shown < whole - SLACK
}

const observer = new ResizeObserver(measure)

onMounted(() => {
  measure()
  if (scroller.value) {
    observer.observe(scroller.value)
    // The content, not only the box: a filtered list is the same box with
    // fewer rows in it, and only the child's size changes.
    if (scroller.value.firstElementChild) observer.observe(scroller.value.firstElementChild)
  }
})

onBeforeUnmount(() => observer.disconnect())
</script>

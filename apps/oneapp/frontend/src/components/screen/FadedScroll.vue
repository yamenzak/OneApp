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
  -->
  <div class="relative min-h-0">
    <div
      ref="scroller"
      class="h-full overflow-y-auto overscroll-contain"
      @scroll.passive="measure"
    >
      <slot />
    </div>

    <div v-if="above" :class="[EDGE, 'top-0 bg-gradient-to-b']" />
    <div v-if="below" :class="[EDGE, 'bottom-0 bg-gradient-to-t']" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

// From the surface behind it to nothing. `from-surface-base` and not a colour:
// the fade has to be the panel's own background or it is a grey band in dark
// mode.
const EDGE =
  'pointer-events-none absolute inset-x-0 z-10 h-6 from-surface-base to-transparent'

const scroller = ref(null)
const above = ref(false)
const below = ref(false)

// A pixel of slack at each end. A scroller sitting exactly at its bottom can
// report a fractional difference on a display with a scale factor, and a fade
// that never quite goes away is worse than one that never appears.
const SLACK = 1

const measure = () => {
  const el = scroller.value
  if (!el) return
  above.value = el.scrollTop > SLACK
  below.value = el.scrollTop + el.clientHeight < el.scrollHeight - SLACK
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

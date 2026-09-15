<template>
  <!--
    The time, at the end of the dock.

    The first inhabitant of the shelf at that end, and the reason the shelf
    exists: what goes there is what is *true right now* rather than somewhere to
    go — the weather after this, and whatever else answers a question you would
    otherwise leave the page to ask. Everything at the other end opens
    something; nothing here does.

    **It reads the workspace's clock, not the browser's.** `lib/runtime/format`
    is the one place in this product that formats a date or a time, and the
    reason is that `toLocaleTimeString` follows the reader's own language and
    region, which nobody configured — so two colleagues would see the same
    workspace on two different clocks, one of them at 4:47 PM and the other at
    16:47, beside a list of times the product had already written its own way.
    `test_one_clock_and_it_is_lib_format` is the guard, and it caught this.

    A minute, not a second. A ticking second hand in the corner of a working
    application is movement in the periphery for no information: nobody times
    anything by it, and the eye goes to whatever moves. The first tick is
    aligned to the next real minute rather than one minute from mount, so two
    browsers open side by side do not disagree for fifty seconds.
  -->
  <Tooltip :text="full">
    <div
      class="flex shrink-0 select-none flex-col items-end leading-tight"
      data-slot="dock-clock"
    >
      <span class="text-sm tabular-nums text-ink-primary">{{ clock }}</span>
      <span class="text-xs tabular-nums text-ink-muted">{{ day }}</span>
    </div>
  </Tooltip>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { Tooltip } from '@/ui'
import { date, moment, time } from '@/shared/lib/runtime/format'

const clock = ref('')
const day = ref('')
const full = ref('')

function now() {
  // A `Date` rather than a string: `format` reads one as the absolute instant
  // it is, which is what a clock is. A Frappe datetime string is the other
  // case — a wall clock in the site's zone — and this is not one.
  const at = new Date()
  // `toTheMinute`, so a workspace whose time pattern carries seconds does not
  // get a dock that redraws a number it is only right about for one second in
  // sixty.
  clock.value = time(at, { toTheMinute: true })
  day.value = date(at)
  full.value = moment(at)
}

now()

// Aligned to the next minute rather than one minute from now, then every
// minute after it. A `setInterval` from mount drifts against the wall clock by
// however long ago the page was opened, so the display changes at :37 past.
let timer = null
const untilTheMinute = () => 60_000 - (Date.now() % 60_000)

function tick() {
  now()
  timer = setTimeout(tick, untilTheMinute())
}

onMounted(() => {
  timer = setTimeout(tick, untilTheMinute())
})
onBeforeUnmount(() => clearTimeout(timer))
</script>

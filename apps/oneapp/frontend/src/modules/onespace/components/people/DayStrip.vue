<template>
  <!--
    Somebody's recent days, as a calendar rather than a ribbon.

    `oneapp/onehr/history.py` answers with one entry per day in the window,
    including the days it knows nothing about — the whole point of a strip is
    that the seventh cell is always the same weekday, and a list of only the
    days Attendance has a row for is a strip with holes that line up with
    nothing.

    Extracted at its second caller and not before: the person record drew this
    for whoever is being read, and the employee's own home draws it for the
    reader. Same window, same vocabulary, same padding rule — and `docs/
    UNIFICATION.md` F1 is entirely about what happens when the *third* caller
    arrives to find the drawing in a file it never opens.
  -->
  <div v-if="days.length" class="flex min-w-0 flex-col gap-1.5">
    <p v-if="weeks" class="text-xs text-ink-muted">
      {{ __('The last {0} weeks', [String(weeks)]) }}
    </p>

    <!--
      Columns of seven, oldest first, so the same weekday is always the same
      row: a person who is out every Thursday is a horizontal line rather than
      a pattern to work out.
    -->
    <div class="flex gap-0.5 overflow-x-auto" data-slot="person-days">
      <div v-for="(week, at) in weekColumns" :key="at" class="flex flex-col gap-0.5">
        <template v-for="(day, row) in week" :key="day?.date || `pad-${at}-${row}`">
          <!--
            A square with a date in a tooltip rather than in a `title`: the
            native one waits a second, cannot be reached from a keyboard and
            renders in the browser's chrome rather than the workspace's theme.
            Fifty-six of them is exactly the case where that matters.
          -->
          <Tooltip v-if="day" :text="`${day.date} · ${dayLook(day.state).label}`">
            <span
              class="size-2.5 rounded-4"
              :class="dayLook(day.state).class"
              :data-state="day.state"
            />
          </Tooltip>
          <span v-else class="size-2.5 rounded-4 bg-transparent" />
        </template>
      </div>
    </div>

    <!--
      Only the states that happened. A legend of six where four never occur
      teaches somebody to read a key that is mostly about nothing, and the two
      that are always there — a working day and a weekend — are the two nobody
      needs told.
    -->
    <div v-if="legend.length" class="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span
        v-for="one in legend"
        :key="one.state"
        class="flex items-center gap-1 text-xs text-ink-muted"
      >
        <span class="size-2 rounded-4" :class="one.class" />
        {{ one.label }}
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { Tooltip } from '@/ui'
import { dayLook } from '@/modules/onespace/lib/screen/presence'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** `[{date, state}]`, every day in the window, oldest first. */
  days: { type: Array, default: () => [] },
  /** How many weeks that is, for the line above it. Zero draws no line. */
  weeks: { type: Number, default: 0 },
})

/**
 * Columns of seven, padded at the front so every row is the same weekday.
 *
 * Without the padding the rows are whatever weekday the window happened to
 * open on, and the one pattern this drawing exists to make visible is exactly
 * the one that gets lost.
 */
const weekColumns = computed(() => {
  const found = props.days
  if (!found.length) return []
  // Monday first: `getDay()` is Sunday-zero, and a week that starts on Sunday
  // puts the weekend either side of the working days it is meant to bracket.
  const first = (new Date(`${found[0].date}T00:00:00`).getDay() + 6) % 7
  const padded = [...Array(first).fill(null), ...found]
  const out = []
  for (let at = 0; at < padded.length; at += 7) out.push(padded.slice(at, at + 7))
  return out
})

/** The states this window actually contains, in reading order. */
const legend = computed(() => {
  const seen = new Set(props.days.map((one) => one.state))
  return ['absent', 'leave', 'half', 'present']
    .filter((state) => seen.has(state))
    .map((state) => ({ state, ...dayLook(state) }))
})
</script>

<template>
  <!--
    Rows against days. One field's values down the side, a month across the
    top, one cell per record.

    The shape a list cannot be, and the reason this is a view type rather than
    a screen: attendance is one row per person per day, and reading it as a
    list means holding eight people by thirty days in your head to answer "who
    was out on the Tuesday". The same rows drawn as a grid answer that, and the
    patterns nobody thought to ask about, without being read at all — a row of
    red is somebody in trouble and a column of it is a day something happened.

    Read-only. A cell opens its record, which is where the day's verdict is
    changed with the doctype's own rules in front of it. A grid that wrote on
    click would be a second save path over the one screen where a mistake is
    somebody's pay.
  -->
  <div class="flex min-h-0 flex-1 flex-col">
    <!-- Which month. The only control, because the only thing to choose. -->
    <div class="flex items-center gap-2 border-b border-outline-gray-2 px-3 py-2">
      <Button
        variant="ghost"
        icon="lucide-chevron-left"
        :label="__('The month before')"
        :tooltip="__('The month before')"
        @click="step(-1)"
      />
      <span data-slot="matrix-month" class="min-w-36 text-center text-base-medium text-ink-primary">
        {{ monthLabel }}
      </span>
      <Button
        variant="ghost"
        icon="lucide-chevron-right"
        :label="__('The month after')"
        :tooltip="__('The month after')"
        @click="step(1)"
      />
      <Button class="ms-1" variant="subtle" :label="__('This month')" @click="step(0)" />

      <!-- Only the states that happened, in reading order. A key of six where
           four never occur teaches somebody to read a key about nothing. -->
      <div v-if="legend.length" class="ms-auto flex flex-wrap items-center gap-x-3 gap-y-1">
        <span
          v-for="one in legend"
          :key="one.label"
          class="flex items-center gap-1.5 text-xs text-ink-muted"
        >
          <span class="size-2.5 rounded-4" :class="one.class" />
          {{ one.label }}
        </span>
      </div>
    </div>

    <EmptyState
      v-if="!rows.length"
      class="flex-1"
      icon="lucide-table-2"
      :title="__('Nothing this month')"
      :description="__('Try another month, or widen the filters.')"
    />

    <!--
      One scroller for both axes, with the names frozen. A grid whose row
      labels scroll away is a grid you cannot read past the second week.
    -->
    <div v-else class="min-h-0 flex-1 overflow-auto" data-slot="matrix">
      <!--
        The rule this suppresses is against hand-rolling a *list*, and
        `ListView` is the answer to that. This is genuinely two-dimensional: a
        frozen column of names against thirty-one day columns, both axes
        scrolling under one pair of sticky headers — which is what `<table>` is
        for and what no list component expresses.
      -->
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
      <table class="border-separate border-spacing-0">
        <thead>
          <tr>
            <th
              class="sticky start-0 top-0 z-20 border-b border-e border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-start text-xs font-normal text-ink-muted"
            >{{ rowLabel }}</th>
            <th
              v-for="day in days"
              :key="day.date"
              class="sticky top-0 z-10 border-b border-outline-gray-2 bg-surface-gray-1 px-1 py-2 text-xs font-normal"
              :class="day.weekend ? 'text-ink-gray-4' : 'text-ink-muted'"
            >
              <span class="block leading-tight">{{ day.weekday }}</span>
              <span class="block tabular-nums leading-tight">{{ day.number }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in lines" :key="line.key" data-slot="matrix-row">
            <th
              class="sticky start-0 z-10 max-w-48 truncate border-b border-e border-outline-gray-2 bg-surface-base px-3 py-1.5 text-start text-sm font-normal text-ink-primary"
              :title="line.label"
            >{{ line.label }}</th>
            <td
              v-for="day in days"
              :key="day.date"
              class="border-b border-outline-gray-2 p-0.5 text-center"
              :class="day.weekend ? 'bg-surface-gray-1' : ''"
            >
              <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a cell in a grid of hundreds; a <Button> brings a height, a padding and a ring into a 24px square, and the whole drawing is the colour -->
              <button
                v-if="line.cells[day.date]"
                type="button"
                class="size-6 rounded-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
                :class="look(line.cells[day.date]).class"
                :title="`${line.label} · ${day.date} · ${look(line.cells[day.date]).label}`"
                :data-cell="look(line.cells[day.date]).label"
                @click="emit('open', line.cells[day.date])"
              />
              <span v-else class="block size-6" aria-hidden="true" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Button } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { valueTheme } from '@/modules/onespace/lib/screen/fields'
import { month as monthName, weekday } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The resolved screen: columns, states, permissions. */
  spec: { type: Object, required: true },
  /** The records in the month on screen, fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields the axes are, as the last page came back for them. The shell
   * owns this because it owns the request — the same reason the calendar's
   * pair is a prop rather than something read off the spec.
   */
  matrix: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'range'])

/** How many rows a grid draws before it is a report. */
const LINES = 60

/**
 * A cell's ground, by the theme its status already earns.
 *
 * `valueTheme` is what the badge on the same record reads, so a grid and a
 * badge cannot disagree about what red means. Written out as literals because
 * Tailwind's JIT reads source rather than a running page — the same reason the
 * icon sets are closed.
 */
const GROUNDS = {
  green: 'bg-surface-green-3',
  red: 'bg-surface-red-3',
  amber: 'bg-surface-amber-3',
  blue: 'bg-surface-blue-3',
  teal: 'bg-surface-green-3',
  orange: 'bg-surface-amber-3',
  pink: 'bg-surface-red-3',
  violet: 'bg-surface-blue-3',
  gray: 'bg-surface-gray-4',
}

/** Which month is on screen, as the first of it. */
const month = ref(first(new Date()))

function first(when) {
  return new Date(when.getFullYear(), when.getMonth(), 1)
}

/** `YYYY-MM-DD` in the reader's own month, never through UTC — `toISOString`
 *  on the first of a month west of Greenwich is the last of the one before. */
function stamp(when) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
}

const days = computed(() => {
  const found = []
  const when = new Date(month.value)
  while (when.getMonth() === month.value.getMonth()) {
    const day = when.getDay()
    found.push({
      date: stamp(when),
      number: when.getDate(),
      weekday: weekday(new Date(when)),
      // Saturday and Sunday, which is what the ground under a cell says and
      // not what the workspace's holiday list says — that is a fact about a
      // person's shift and this is a fact about the calendar.
      weekend: day === 0 || day === 6,
    })
    when.setDate(when.getDate() + 1)
  }
  return found
})

const monthLabel = computed(() => monthName(month.value))

const rowField = computed(() => props.matrix?.row_field || '')
const dateField = computed(() => props.matrix?.date_field || '')
const valueField = computed(() => props.matrix?.value_field || '')

const rowLabel = computed(() => {
  const found = (props.spec?.all_columns || props.spec?.columns || [])
    .find((one) => one.fieldname === rowField.value)
  return found?.label || ''
})

/**
 * The rows, grouped down the side.
 *
 * The label is the Link's own — `_links` carries what the target's title field
 * says, resolved once for the page — because a grid down the side of
 * `HR-EMP-00003` is a grid nobody reads. Sorted by that label, so the same
 * month looks the same twice.
 */
const lines = computed(() => {
  const field = rowField.value
  const date = dateField.value
  if (!field || !date) return []

  const by = new Map()
  for (const row of props.rows) {
    const key = row[field]
    if (!key) continue
    if (!by.has(key)) {
      by.set(key, {
        key,
        label: row._links?.[field]?.label || String(key),
        cells: {},
      })
    }
    // The day, as the server wrote it. A datetime carries a time after it.
    by.get(key).cells[String(row[date]).slice(0, 10)] = row
  }
  return [...by.values()]
    .sort((a, b) => a.label.localeCompare(b.label))
    .slice(0, LINES)
})

/** What a cell is coloured by: the screen's own states, so a grid and a badge
 *  on the same record agree about what red means. */
const look = (row) => {
  const value = valueField.value ? String(row[valueField.value] || '') : ''
  // The screen's own declaration first, then the states the doctype ships,
  // then the words. A cell is nothing but its colour, so a screen that cared
  // enough to say is the answer — and everything else still gets the same
  // colour its badge has.
  const theme = props.matrix?.colours?.[value]
    || valueTheme(value, props.spec?.states || [])
  return { label: value, class: GROUNDS[theme] || GROUNDS.gray }
}

const legend = computed(() => {
  const seen = new Map()
  for (const line of lines.value) {
    for (const row of Object.values(line.cells)) {
      const found = look(row)
      if (found.label && !seen.has(found.label)) seen.set(found.label, found)
    }
  }
  return [...seen.values()]
})

/** Which days to ask the server for. The month, and nothing either side of
 *  it: a grid draws the month it says it is drawing. */
const asked = computed(() => ({
  since: days.value[0]?.date || '',
  until: days.value[days.value.length - 1]?.date || '',
}))

watch(asked, (now) => {
  if (now.since && now.until) emit('range', now)
}, { immediate: true })

const step = (by) => {
  month.value = by
    ? new Date(month.value.getFullYear(), month.value.getMonth() + by, 1)
    : first(new Date())
}
</script>

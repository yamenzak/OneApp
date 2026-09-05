<template>
  <!--
    The Gantt: the same rows, drawn as bars down time.

    Same rows, same filters, same order as every other body — what changes is
    that a record with two dates on it becomes a length rather than a line. It
    is the view for the question a list cannot answer without arithmetic: what
    overlaps what, and what is late.

    The chart is `frappe-gantt`, Frappe's own MIT package, so this is a
    dependency and not a vendoring. It draws into a plain element from a list
    of `{id, name, start, end, progress}`, which is the whole of what this
    component does — that, and taking a click back to the record.

    A page rather than a range, unlike the calendar: a plan is read whole, and
    "the bars that happen to be in September" is not a plan.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="gantt">
    <EmptyState
      v-if="!field"
      icon="lucide-chart-no-axes-gantt"
      title="No dates to draw"
      description="This screen offers a Gantt but names no pair of dates for it."
    />
    <EmptyState
      v-else-if="!bars.length"
      icon="lucide-chart-no-axes-gantt"
      title="Nothing to plot"
      description="None of these records has both a start and an end."
    />
    <!-- `v-show` and not `v-else`: the chart draws into this element on mount,
         and an element `v-if` has removed is one the library holds a dead
         reference to the moment a filter empties the page. -->
    <div v-show="bars.length" ref="canvas" class="w-full" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Gantt from 'frappe-gantt'
import 'frappe-gantt/style.css'
import EmptyState from '../../EmptyState.vue'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields the two ends are, as the last page came back for them — the
   * same reason the board's column field is handed down rather than read from
   * the spec: the shell owns the request.
   */
  gantt: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open'])

const canvas = ref(null)
let chart = null

const field = computed(() => props.gantt?.start_field || '')
const endField = computed(() => props.gantt?.end_field || '')
const measure = computed(() => props.gantt?.progress_field || '')

/** What a record is called, from the doctype's own title field. */
const nameOf = (row) => {
  const title = props.spec?.title_field
  return String((title && row[title]) || row.name || '')
}

/** The day part of a Date or a Datetime. See `CalendarBody`. */
const day = (value) => String(value || '').trim().split(' ')[0]

const bars = computed(() => {
  if (!field.value || !endField.value) return []
  return props.rows
    .map((row) => {
      const from = day(row[field.value])
      const to = day(row[endField.value])
      // Both ends or no bar. A record with one date is a moment, and drawing
      // it as a bar of arbitrary length would be inventing a plan.
      if (!from || !to) return null
      return {
        id: row.name,
        name: nameOf(row),
        start: from,
        // A bar that ends before it starts is a typo in the data rather than a
        // shape to draw: shown as a single day, which is what it is.
        end: to < from ? from : to,
        progress: measure.value ? Number(row[measure.value]) || 0 : 0,
      }
    })
    .filter(Boolean)
})

/**
 * Read-only, like the calendar and for the same reason.
 *
 * Dragging a bar writes two fields on a record, and this screen already writes
 * them properly — with the doctype's rules, its permissions and whatever else
 * depends on them. `readonly` rather than leaving the handles on and ignoring
 * what they emit: a control that moves and then springs back is worse than one
 * that does not move.
 */
const OPTIONS = {
  readonly: true,
  view_mode: 'Week',
  // Frappe's own default set, minus the ones that make no sense at this
  // scale: Hour is a chart of one afternoon and Year is a chart of nothing.
  view_mode_select: true,
  popup: false,
}

function draw() {
  if (!canvas.value || !bars.value.length) return
  if (chart) {
    chart.refresh(bars.value)
    return
  }
  chart = new Gantt(canvas.value, bars.value, {
    ...OPTIONS,
    on_click: (task) => {
      const row = props.rows.find((one) => one.name === task?.id)
      if (row) emit('open', row)
    },
  })
}

onMounted(draw)
watch(bars, draw)

onBeforeUnmount(() => {
  // The library binds to the element and to `window`; leaving it attached
  // after the body swaps is a listener drawing into a detached tree.
  chart?.clear?.()
  chart = null
})
</script>

<style>
/*
 * The chart, in this product's colours.
 *
 * `frappe-gantt` ships its own palette on `:root` with a dark set behind
 * `html[data-theme=dark]` — which is our attribute, but only when a reader has
 * *chosen* a mode: on the default "system" setting nothing is stamped and the
 * chart would draw a white grid on a dark page. So the variables are taken from
 * frappe-ui's tokens instead, which resolve in all three states and which every
 * other surface in the app is already painted from.
 *
 * Unscoped because the library draws into an element it owns rather than into
 * this template, so a `scoped` attribute would never reach it. Confined to
 * `.gantt-container`, which is the library's own root and nothing else's.
 */
.gantt-container {
  --g-header-background: var(--surface-base);
  --g-row-color: var(--surface-base);
  --g-row-border-color: var(--outline-gray-2);
  --g-border-color: var(--outline-gray-1);
  --g-tick-color: var(--outline-gray-1);
  --g-tick-color-thick: var(--outline-gray-2);
  --g-weekend-highlight-color: var(--surface-gray-1);
  --g-weekend-label-color: var(--surface-gray-3);
  --g-actions-background: var(--surface-gray-2);
  --g-popup-actions: var(--surface-gray-2);
  --g-bar-color: var(--surface-gray-2);
  --g-bar-border: var(--outline-gray-2);
  --g-progress-color: var(--surface-gray-5);
  --g-expected-progress: var(--surface-gray-3);
  --g-arrow-color: var(--ink-gray-5);
  --g-handle-color: var(--ink-gray-8);
  --g-today-highlight: var(--ink-gray-8);
  --g-text-dark: var(--ink-gray-8);
  --g-text-muted: var(--ink-gray-5);
  --g-text-light: var(--surface-base);
}

/* The library sets its own stack; the rest of the app is on frappe-ui's. */
.gantt-container .bar-label {
  font-family: inherit;
}
</style>

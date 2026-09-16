<template>
  <!--
    The Gantt: the same rows, drawn as bars down time. The view for the question
    a list cannot answer without arithmetic — what overlaps what, and what is
    late.

    The chart is `frappe-gantt`, Frappe's own MIT package, so this is a
    dependency and not a vendoring. A page rather than a range, unlike the
    calendar: a plan is read whole.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="gantt">
    <EmptyState
      v-if="!field"
      icon="lucide-chart-no-axes-gantt"
      :title="__('No dates to draw')"
      :description="__('This screen shows a Gantt, but no fields on it say when a record starts and ends.')"
    />
    <EmptyState
      v-else-if="!bars.length"
      icon="lucide-chart-no-axes-gantt"
      :title="__('Nothing to plot')"
      :description="__('None of these records has both a start and an end.')"
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
import { identityOf } from '@/modules/onespace/lib/screen/identity'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields the two ends are, as the last page came back for them — handed
   * down for the same reason the board's column field is: the shell owns the
   * request.
   */
  gantt: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open'])

const canvas = ref(null)
let chart = null

const field = computed(() => props.gantt?.start_field || '')
const endField = computed(() => props.gantt?.end_field || '')
const measure = computed(() => props.gantt?.progress_field || '')
const depends = computed(() => props.gantt?.depends_field || '')
// Whether that field is a table of edges rather than a single Link.
const through = computed(() => props.gantt?.depends_child || '')
// Which records are dates the plan is measured by rather than work in it.
const mark = computed(() => props.gantt?.milestone_field || '')

/** What a record is called — `lib/screen/identity.js`, the same reading every
 *  other surface does, including a Link title drawn as its label. */
const nameOf = (row) => identityOf(row, props.spec).label

/** The day part of a Date or a Datetime. See `CalendarBody`. */
const day = (value) => String(value || '').trim().split(' ')[0]

/**
 * The bar this one comes after, where the screen names a field for it.
 *
 * Bounded to the page: the chart resolves a dependency by looking the id up in
 * the list it was handed, so a predecessor on page two is an arrow that appears
 * and disappears as somebody presses Load more.
 */
const onPage = computed(() => new Set(props.rows.map((row) => row.name)))

/**
 * What this bar comes after.
 *
 * Two shapes, and the screen has already been told which it is. A **Link** is
 * one predecessor, read off the record. A **table** is the task's own edges,
 * which the server attached to the page as `_after` — one query for the whole
 * chart rather than one per bar. `onespace/spaceview/records.py`.
 */
const waiting = (row) => {
  if (!depends.value) return []
  const after = through.value ? row._after || [] : [String(row[depends.value] || '')]
  return after.filter((one) => one && one !== row.name && onPage.value.has(one))
}

const bars = computed(() => {
  if (!field.value || !endField.value) return []
  return props.rows
    .map((row) => {
      const marker = mark.value && !!row[mark.value]
      const from = day(row[field.value])
      // A milestone is a date, not a stretch of work: whichever end it has is
      // both of them. Without this a launch date with no start was left off
      // the chart it is the point of.
      const to = marker ? day(row[endField.value]) || from : day(row[endField.value])
      // Both ends or no bar. A record with one date is a moment, and drawing it
      // as a bar of arbitrary length would be inventing a plan.
      if (!from || !to) return null
      return {
        custom_class: marker ? 'oneapp-milestone' : '',
        id: row.name,
        name: nameOf(row),
        start: from,
        // A bar that ends before it starts is a typo in the data rather than a
        // shape to draw: shown as a single day.
        end: to < from ? from : to,
        progress: measure.value ? Number(row[measure.value]) || 0 : 0,
        // What this one waits on. Only where the bar it names is on this page —
        // an arrow to nothing is a line into the margin.
        dependencies: waiting(row),
      }
    })
    .filter(Boolean)
})

/**
 * Read-only, like the calendar and for the same reason: dragging a bar writes
 * two fields, and this screen already writes them properly. `readonly` rather
 * than ignoring what the handles emit — a control that moves and springs back
 * is worse than one that does not move.
 */
const OPTIONS = {
  readonly: true,
  view_mode: 'Week',
  /*
   * Framed on the first bar rather than on today, which is the library's
   * default and the wrong one here.
   *
   * A Gantt in this product is a *view of a page of records* — somebody
   * filtered a list and asked to see it as bars. Opening on today means a
   * screen of seventeen tasks whose work is behind them shows ten empty rows
   * and three bars hugging the left edge, and the reader's first action is to
   * scroll back to the data they just asked for. The library draws a Today
   * button in its own header, so the other direction costs one click and this
   * one costs none.
   */
  scroll_to: 'start',
  // Frappe's own default set, minus the ones that make no sense at this scale:
  // Hour is a chart of one afternoon and Year is a chart of nothing.
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
  // The library binds to the element and to `window`; leaving it attached after
  // the body swaps is a listener drawing into a detached tree.
  chart?.clear?.()
  chart = null
})
</script>

<style>
/*
 * The chart, in this product's colours.
 *
 * `frappe-gantt` ships its own palette behind `html[data-theme=dark]` — our
 * attribute, but only stamped when a reader has *chosen* a mode, so on the
 * default "system" setting the chart drew a white grid on a dark page. The
 * variables come from frappe-ui's tokens instead, which resolve in all three
 * states.
 *
 * Unscoped because the library draws into an element it owns, so a `scoped`
 * attribute would never reach it. Confined to `.gantt-container`.
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
  /*
   * The bar, and the part of it that is done.
   *
   * Both were greys a step apart from the row they sit on — `gray-2` on
   * `surface-base` — which on a screen of forty rows is a chart you have to
   * lean into. A Gantt is *read as a picture*: where the bars are, how long
   * they are, how full. So the trough is a surface you can see the edge of and
   * the fill is `gray-10`, which is where a space's declared accent lands
   * (`onespace/theming.py`) — the same colour as the progress fill everywhere
   * else in the product, which is what that token is for.
   *
   * The fill matters on a screen that names no `progress_field` too: there the
   * bar is all trough, and the trough has to hold its own.
   */
  --g-bar-color: var(--surface-gray-3);
  --g-bar-border: var(--outline-gray-3);
  --g-progress-color: var(--surface-gray-10);
  --g-expected-progress: var(--surface-gray-4);
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

/*
 * Today's line is a decoration and was eating clicks.
 *
 * `frappe-gantt` draws it as a full-height `div` over the chart, so any bar
 * crossing today could not be opened — the click landed on the highlight and
 * the record never came up. It was always true and it took framing the chart on
 * its first bar to make it likely enough to notice, which is the kind of bug
 * that reads as "the Gantt is sometimes broken".
 */
.gantt-container .current-highlight,
.gantt-container .current-date-highlight {
  pointer-events: none;
}

/*
 * A milestone is a date the plan is measured by, and it is the one row on a
 * Gantt that is not a stretch of work: a launch, a handover, an inspection.
 *
 * Turned forty-five degrees and squared off — the diamond every plan in the
 * world draws — rather than given a colour of its own, because a chart where
 * the difference between "work" and "a date" is a hue is a chart that has to
 * be explained. The label is rotated back so it stays readable.
 */
.gantt-container .oneapp-milestone .bar,
.gantt-container .oneapp-milestone .bar-progress {
  fill: var(--ink-gray-8);
  transform-box: fill-box;
  transform-origin: center;
  transform: rotate(45deg) scale(0.7);
}

.gantt-container .oneapp-milestone .bar-label {
  font-weight: 600;
}
</style>

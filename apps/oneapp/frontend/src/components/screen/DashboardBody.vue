<template>
  <!--
    The dashboard: a screen's rows counted rather than listed.

    The fourth body, and the first that does not draw records. A list, a board
    and a grid all answer "which rows"; this answers "how many, how much, and
    which way is it going" — so it reads none of the props the others share
    except the two that decide what it is measuring, and it fetches its own
    numbers rather than plotting the page of rows the shell has.

    That is the whole reason it is a separate request: the shell's page is
    twenty rows and a chart is about all of them.

    It still obeys the toolbar. The same filters the list is narrowed by go to
    the server with the widgets, so a dashboard beside a filtered list is
    answering the same question the list is — a chart that ignored the filter
    above it would be a chart that quietly disagrees with its own screen.
  -->
  <div class="min-h-0 flex-1 overflow-y-auto">
    <EmptyState
      v-if="!loading && !widgets.length"
      icon="lucide-chart-column"
      title="Nothing to measure"
      description="This screen offers a dashboard but declares no widgets."
    />

    <!--
      Twelve columns, because that is the grid a width of 3, 4, 6, 8 or 12
      divides evenly — and one column on a phone, because a plot narrower than
      a thumb is a plot nobody can read.
    -->
    <div v-else class="grid grid-cols-1 items-start gap-3 p-3 md:grid-cols-12">
      <!--
        A height, and it has to be here. Every plot in the family measures its
        container and draws into a canvas that size — so a widget in a grid
        cell with no height of its own gets a canvas one pixel tall, which
        renders as a title with nothing under it and no error anywhere. A
        number card is type rather than a plot and sizes itself.
      -->
      <div
        v-for="widget in widgets"
        :key="widget.label"
        :data-oneapp-widget="widget.kind"
        :class="[span(widget.width), height(widget)]"
      >
        <DashboardWidget :widget="widget" :loading="loading" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import EmptyState from '../EmptyState.vue'
import DashboardWidget from './DashboardWidget.vue'
import { workspace } from '../../lib/workspace'
import { notifyError } from '../../lib/notify'

// Written out rather than built, because Tailwind only emits CSS for class
// names it can see: `md:col-span-${n}` compiles to nothing at all, and the
// widgets would all sit at full width with no error anywhere.
const SPANS = {
  3: 'md:col-span-3',
  4: 'md:col-span-4',
  6: 'md:col-span-6',
  8: 'md:col-span-8',
  12: 'md:col-span-12',
}

const props = defineProps({
  /** The resolved screen. `spec.widgets` is the declaration, without numbers. */
  spec: { type: Object, required: true },
  spaceCode: { type: String, default: '' },
  /** The saved view in force, so the charts read what the list reads. */
  layout: { type: String, default: '' },
  /** Filters and sort somebody changed and has not saved. */
  overrides: { type: Object, default: null },
  // Declared so the shell can bind one set of props to every body. A dashboard
  // draws no rows and ticks none: what it measures is every row that matches,
  // not the page of them the shell happens to be holding.
  rows: { type: Array, default: () => [] },
  columns: { type: Array, default: () => [] },
  orderBy: { type: String, default: '' },
  favourites: { type: Boolean, default: false },
  counted: { type: String, default: '' },
  groupBy: { type: String, default: '' },
  board: { type: Object, default: () => ({}) },
  cards: { type: Object, default: () => ({}) },
})

defineModel('selection', { type: Array, default: () => [] })
defineEmits(['open', 'like', 'sort', 'favourites', 'change', 'new'])

const widgets = ref([])
const loading = ref(false)

const span = (width) => SPANS[width] || SPANS[6]

// A plot measures its container and draws into an SVG that size, so a widget
// in a grid cell with no height of its own gets one a pixel tall — a title
// with nothing under it, and no error anywhere. A number card is type rather
// than a plot and sizes itself.
//
// Worked out here rather than as a ternary in the template: the design-token
// guard reads `:class` bindings looking for class names, and the branch that
// is not one reads as a class that emits no CSS.
const height = (widget) => (widget.kind === 'number' ? '' : 'h-72')

const load = async () => {
  if (!props.spec?.doctype) return
  loading.value = true
  try {
    const found = await workspace.dashboard(props.spaceCode, props.spec.screen, {
      layout: props.layout,
      overrides: props.overrides,
    })
    widgets.value = found?.widgets || []
  } catch (raised) {
    notifyError(raised.message || String(raised))
    widgets.value = []
  } finally {
    loading.value = false
  }
}

// The screen, the saved view and the unsaved filter — the same three the shell
// re-fetches its rows on. A chart that did not follow them would be a chart
// answering the question the reader asked two filters ago.
watch(
  [() => props.spec?.screen, () => props.layout, () => props.overrides],
  load,
  { immediate: true, deep: true },
)
</script>

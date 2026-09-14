<template>
  <!--
    The dashboard: a screen's rows counted rather than listed.

    The first body that does not draw records — it answers "how many, how much,
    and which way is it going", so it fetches its own numbers rather than
    plotting the page of rows the shell has. The shell's page is twenty rows and
    a chart is about all of them.

    It still obeys the toolbar: the same filters go to the server with the
    widgets, so a dashboard beside a filtered list answers the same question.
  -->
  <div class="min-h-0 flex-1 overflow-y-auto">
    <EmptyState
      v-if="!loading && !widgets.length"
      icon="lucide-chart-column"
      :title="__('Nothing to measure')"
      :description="__('This screen shows a dashboard, but nothing has been added to it to count.')"
    />

    <template v-else>
      <!--
        The one control a dashboard has of its own, and only where the screen
        named a date for it. Almost every question a dashboard answers has an
        unspoken "…lately" on the end, and asking it through the Filter control
        means picking a field, an operator and two dates to say "this quarter".

        It writes an ordinary filter — see `lib/screen/periods.js` — so what it
        did is visible in the Filter control afterwards, where it can be read,
        changed or taken off.
      -->
      <div
        v-if="periodField"
        data-slot="dashboard-period"
        class="flex items-center gap-2 border-b border-outline-gray-2 px-3 py-2"
      >
        <Icon name="lucide-calendar-range" class="size-4 shrink-0 text-ink-muted" />
        <Select
          v-model="period"
          class="w-48"
          :options="PERIODS.map((one) => ({ label: one.label, value: one.value }))"
        />
        <span class="truncate text-xs text-ink-muted">{{ periodLabel }}</span>
      </div>

      <!-- Twelve columns, the grid a width of 3, 4, 6, 8 or 12 divides evenly
           — and one column on a phone. -->
      <div class="grid grid-cols-1 items-start gap-3 p-3 md:grid-cols-12">
      <!--
        A height, and it has to be here: every plot measures its container and
        draws into a canvas that size, so a widget in a grid cell with no height
        of its own gets a canvas one pixel tall.
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
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import DashboardWidget from '@/modules/onespace/components/screen/bodies/DashboardWidget.vue'
import { DEFAULT_PERIOD, PERIODS, spanOf } from '@/modules/onespace/lib/screen/periods'
import { date as onDate } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'
import { workspace } from '@/shared/lib/workspace'
import { notifyError } from '@/shared/lib/runtime/notify'

// Written out rather than built, because Tailwind only emits CSS for class
// names it can see: `md:col-span-${n}` compiles to nothing at all.
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
  // draws no rows and ticks none.
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
const emit = defineEmits([
  'open', 'like', 'sort', 'favourites', 'change', 'new', 'narrow',
])

/**
 * The date this dashboard is about, where the screen named one.
 *
 * Absent for most screens, and then there is no control — a period over a
 * doctype with no date worth narrowing by would be a control that answers a
 * question nobody has.
 */
const periodField = computed(() => props.spec?.dashboard?.period_field || '')

const period = ref(DEFAULT_PERIOD)

/** The span in the reader's own words, beside the control. Two dates read
 *  faster than "this quarter" when somebody is checking what they are seeing. */
const periodLabel = computed(() => {
  const span = spanOf(period.value)
  return span ? `${onDate(span[0])} – ${onDate(span[1])}` : ''
})

/**
 * Narrowing through the ordinary filter path — see `lib/screen/periods.js`.
 *
 * The shell re-fetches on a filter change, so this does not reload the widgets
 * itself: the overrides come back down as a prop and the watcher below is what
 * asks the server again. One path, and the Filter control shows what happened.
 */
watch(period, (chosen) => {
  const span = spanOf(chosen)
  emit('narrow', span
    ? { field: periodField.value, operator: 'between', value: span }
    : { field: periodField.value, value: null })
})

const widgets = ref([])
const loading = ref(false)

const span = (width) => SPANS[width] || SPANS[6]

// A plot measures its container and draws into an SVG that size, so a widget in
// a grid cell with no height of its own gets one a pixel tall. Worked out here
// rather than as a ternary in the template: the design-token guard reads
// `:class` bindings looking for class names.
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
    notifyError(raised)
    widgets.value = []
  } finally {
    loading.value = false
  }
}

// The screen, the saved view and the unsaved filter — the same three the shell
// re-fetches its rows on.
watch(
  [() => props.spec?.screen, () => props.layout, () => props.overrides],
  load,
  { immediate: true, deep: true },
)
</script>

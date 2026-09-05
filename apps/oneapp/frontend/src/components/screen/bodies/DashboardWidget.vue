<template>
  <!--
    One widget: a reading or a plot, over numbers the server already shaped.

    The shaping is deliberately not here. The same aggregate feeds a number
    card and a donut, and two shapings of one answer is how a dashboard comes
    to disagree with itself — so `oneapp_core/dashboard.py` returns rows of
    `{label, value}` (plus `series` where there is one) and this decides only
    which frappe-ui component reads them and with which keys.

    `<component :is>` over a lookup rather than a v-if ladder: nine kinds is
    nine branches that all say the same thing, and the tenth is then a tenth
    branch instead of a row in a table.
  -->
  <ChartCard v-if="!component" :card="true">
    <ChartContainer :title="widget.label" error="This kind of chart is not built." />
  </ChartCard>

  <NumberCard
    v-else-if="widget.kind === 'number'"
    :title="widget.label"
    :value="widget.value ?? 0"
    :prefix="widget.prefix"
    :suffix="widget.suffix"
    :loading="loading"
    compact
  />

  <component
    v-else
    :is="component"
    v-bind="plot"
    :title="widget.label"
    :loading="loading"
    :empty="!rows.length"
  />
</template>

<script setup>
import { computed } from 'vue'
import {
  AreaChart,
  BarChart,
  ChartCard,
  ChartContainer,
  DonutChart,
  FunnelChart,
  HeatmapChart,
  LineChart,
  NumberCard,
  SankeyChart,
  ScatterChart,
} from '@/ui'

// The server names the component; this is the only place that turns a name
// into one. Keyed by the same string `dashboard.KINDS` carries, so a kind the
// server knows and this does not draws its own error rather than nothing —
// which is what the `v-if` above is for.
const COMPONENTS = {
  AreaChart,
  BarChart,
  DonutChart,
  FunnelChart,
  HeatmapChart,
  LineChart,
  NumberCard,
  SankeyChart,
  ScatterChart,
}

const props = defineProps({
  /** One entry of `dashboard_data().widgets` — the declaration and its data. */
  widget: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})

const component = computed(() => COMPONENTS[props.widget.component] || null)
const rows = computed(() => props.widget.rows || [])

/**
 * The rows as the chart this widget names wants them.
 *
 * Every chart in frappe-ui takes a flat `data` array and the *names of the
 * keys* to read out of it, which is why one server shape feeds all nine: what
 * changes between a donut and a bar is which key is the category and which is
 * the measure, not what a row looks like.
 */
const plot = computed(() => {
  const data = rows.value
  const kind = props.widget.kind

  if (kind === 'donut' || kind === 'funnel') {
    return { data, category: 'label', value: 'value' }
  }
  if (kind === 'heatmap') {
    return { data, x: 'label', y: 'series', value: 'value' }
  }
  if (kind === 'sankey') {
    return { data, source: 'label', target: 'series', value: 'value' }
  }
  if (kind === 'scatter') {
    return {
      data,
      x: 'x',
      y: 'y',
      label: 'label',
      ...(props.widget.series ? { series: 'series' } : {}),
    }
  }

  // The cartesian family — bar, line, area. `series` is the grouping column
  // where the widget has one, which is what turns one line into a line per
  // value of it; frappe-ui reads that as long data and builds the series
  // itself, so there is nothing to pivot here.
  return {
    data,
    x: 'label',
    y: 'value',
    ...(props.widget.series ? { series: 'series' } : {}),
    ...(props.widget.stacked ? { stacked: true } : {}),
    ...(props.widget.horizontal && kind === 'bar' ? { horizontal: true } : {}),
  }
})
</script>

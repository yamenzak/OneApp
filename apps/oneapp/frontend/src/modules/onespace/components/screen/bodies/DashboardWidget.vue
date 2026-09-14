<template>
  <!--
    One widget: a reading or a plot, over numbers the server already shaped.

    The shaping is deliberately not here. The same aggregate feeds a number
    card and a donut, and two shapings of one answer is how a dashboard comes
    to disagree with itself — so `onespace/dashboard.py` returns rows of
    `{label, value}` (plus `series` where there is one) and this decides only
    which frappe-ui component reads them and with which keys.

    `<component :is>` over a lookup rather than a v-if ladder: nine kinds is
    nine branches that all say the same thing, and the tenth is then a tenth
    branch instead of a row in a table.
  -->
  <ChartCard v-if="!component" :card="true">
    <ChartContainer :title="widget.label" :error="__('This kind of chart is not built.')" />
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
import { __ } from '@/shared/lib/runtime/translate'

// The server names the component; this is the only place that turns a name
// into one. Keyed by the same string `dashboard.KINDS` carries, so a kind the
// server knows and this does not draws its own error rather than nothing —
// which is what the `v-if` above is for.
// The key a row carries its own name under. A constant because it is a row
// key rather than a word anybody reads, and `label: 'label'` written inline is
// indistinguishable from a label somebody would want translated.
const LABEL_KEY = 'label'

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
/**
 * The ramp this widget's colours come from.
 *
 * Decided by `onespace/dashboard.py`, because it is a fact about the widget's
 * shape — whether its groups are unrelated categories or steps of one
 * magnitude — and that is what the shaper already knows.
 *
 * One thing was tried and taken out. echarts colours by *series*, so a bar
 * chart of eight departments is eight bars of one colour however the ramp is
 * set; the lever that changes that is `colorBy: 'data'` on the series, and the
 * only way to reach it is `echartOptions`, which frappe-ui offers as a
 * last-resort escape hatch and deep-merges into the built option. It does not
 * survive the merge: as an object over an array and as an array of one, both
 * dropped the plot and left the axis labels standing. A colour that costs the
 * chart is not a trade, and one series being one colour is echarts' own
 * considered default rather than an oversight.
 */
const colours = computed(() => ({ palette: props.widget.palette || 'categorical' }))

const plot = computed(() => {
  const data = rows.value
  const kind = props.widget.kind

  if (kind === 'donut' || kind === 'funnel') {
    // `centerLabel` is the word under the total in the hole. Without it the
    // donut prints the name of the key it read, which is `value`, so every
    // donut in the product said "Value" — see `records._measure`.
    return {
      data,
      category: 'label',
      value: 'value',
      ...(props.widget.measure ? { centerLabel: props.widget.measure } : {}),
      ...colours.value,
    }
  }
  if (kind === 'heatmap') {
    // A heatmap is a single magnitude across a grid, so it keeps the ramp the
    // server sent and never colours by bucket — that is what a heatmap is.
    return { data, x: 'label', y: 'series', value: 'value' }
  }
  if (kind === 'sankey') {
    return { data, source: 'label', target: 'series', value: 'value',
             palette: props.widget.palette || 'categorical' }
  }
  if (kind === 'scatter') {
    return {
      data,
      x: 'x',
      y: 'y',
      label: LABEL_KEY,
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
    ...colours.value,
  }
})
</script>

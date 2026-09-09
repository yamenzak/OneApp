<template>
  <!--
    The aggregate tier, looked at.

    Four figures and five plots, all off `serviceHour` — the tier the nightly
    roll-up writes and nothing deletes. Nothing here is predicted: what a
    Tuesday at eight looks like *is* every Tuesday at eight that has happened,
    which is both more useful to a scheduler and more defensible to a regulator
    than a number a model produced. See `onemobility/README.md` §7a.

    A `component` screen and not a dashboard view, for one reason: a dashboard
    widget counts a doctype's rows, and none of this is a doctype. The
    aggregate tier is outside the document system by design.

    The colours are `lib/palette.js`, which is also what the live map draws
    with — occupancy is the same five bands on both screens, and delay is the
    same diverging ramp. Two views of one set of numbers should not need
    learning twice.
  -->
  <div class="h-full min-h-[28rem] w-full overflow-y-auto" data-slot="insights">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <!-- What is being read, and over how long. One row, above everything. -->
      <div class="flex flex-wrap items-center gap-2" data-slot="insights-controls">
        <Select
          v-model="line"
          :options="lineOptions"
          :placeholder="__('Every line')"
          class="w-52"
        />
        <Select v-model="range" :options="rangeOptions" class="w-40" />
        <span v-if="window" class="ms-auto text-sm text-ink-gray-5">{{ window }}</span>
      </div>

      <EmptyState
        v-if="ready && !headline.length"
        icon="lucide-chart-column"
        :title="__('Nothing measured yet')"
        :description="__('Connect a source and let a day go by, and this fills in.')"
      />

      <template v-else>
        <!--
          The four figures. Each carries the shape it is a summary of, because
          a number with its own history beside it answers "and is that
          unusual" without a second chart.
        -->
        <!-- A height, and it has to be here: a card with a trend across its
             bottom is taller than one with a number in it, and the grid gives
             every cell the height of the shortest unless told otherwise. -->
        <div class="grid auto-rows-[7.5rem] grid-cols-2 gap-3 lg:grid-cols-4">
          <NumberCard
            v-for="one in headline"
            :key="one.label"
            :title="one.label"
            :value="one.value ?? 0"
            :suffix="one.suffix"
            :subtitle="one.subtitle"
            :sparkline="one.sparkline"
            :loading="loading"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-72">
            <!--
              Two reference lines, and they are the point of the chart: zero is
              the timetable, and five minutes is the threshold every European
              authority reports against. A delay plot without them is a wiggle
              nobody can grade.
            -->
            <LineChart
              :data="byHour"
              x="label"
              y="value"
              :title="__('Lateness through the day')"
              :subtitle="__('Seconds behind the timetable, weighted by how much was seen')"
              :reference-lines="lateMarks"
              :palette="[delayInk(240)]"
              :loading="loading"
            />
          </div>
          <div class="h-72">
            <BarChart
              :data="loadByHour"
              x="label"
              y="value"
              :title="__('How full, through the day')"
              :subtitle="__('Percent of capacity')"
              :palette="[occupancyInk(60)]"
              :loading="loading"
            />
          </div>
        </div>

        <div class="h-96">
          <HeatmapChart
            :data="week"
            x="label"
            y="series"
            value="value"
            :title="__('The week')"
            :subtitle="__('How full each line runs, by hour and weekday')"
            :loading="loading"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <div class="h-80 lg:col-span-2">
            <BarChart
              :data="byLine"
              x="label"
              y="value"
              horizontal
              :title="__('Which lines run late')"
              :subtitle="__('Average minutes behind the timetable, every line')"
              palette="categorical"
              :loading="loading"
            />
          </div>
          <div class="h-80">
            <!--
              Early and late are opposite failures with opposite fixes — a bus
              running early has left a stop before anybody got to it — so they
              are two bars and not one figure. Coloured off the same diverging
              ramp as the plot above, cool for early and warm for late.
            -->
            <BarChart
              :data="punctualitySplit"
              x="label"
              :y="['early', 'on_time', 'late']"
              horizontal
              stacked
              :title="__('Against the timetable')"
              :subtitle="__('Readings either side of the on-time window')"
              :series-config="punctualityConfig"
              :loading="loading"
            />
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { BarChart, HeatmapChart, LineChart, NumberCard, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { delayInk, divergingRamp, occupancyInk } from '@/modules/onemobility/lib/palette'

defineProps({
  /** The resolved screen. Unused: this surface reads no records. */
  spec: { type: Object, default: () => ({}) },
})

const line = ref('')
const range = ref('30')
const ready = ref(false)
const loading = ref(true)
const answer = ref({})

const byHour = computed(() => answer.value.by_hour || [])
const loadByHour = computed(() => answer.value.load_by_hour || [])
const week = computed(() => answer.value.week || [])
const byLine = computed(() => answer.value.by_line || [])
const punctuality = computed(() => answer.value.punctuality || [])

/**
 * The headline figures, each given what a card can carry beyond the number:
 * the series it summarises, and the colour that says whether it is good.
 */
const headline = computed(() =>
  (answer.value.headline || []).map((one) => {
    if (one.label === __('Average delay')) {
      return {
        ...one,
        subtitle: __('Across the whole window'),
        // A line, because lateness is a continuous reading — and in the
        // diverging ramp's warm step, so the card and the plot under it are
        // saying the same thing in the same colour.
        sparkline: {
          data: (answer.value.by_hour || []).map((row) => row.value),
          type: 'line',
          color: delayInk(240),
        },
      }
    }
    if (one.label === __('Readings')) {
      return {
        ...one,
        subtitle: __('Positions the fleet reported'),
        // Bars, because these are counted in periods rather than measured.
        sparkline: {
          data: (answer.value.service_by_hour || []).map((row) => row.value),
          type: 'bar',
        },
      }
    }
    if (one.label === __('On time')) {
      return {
        ...one,
        subtitle: __('Within a minute early and five late'),
        sparkline: {
          data: (answer.value.punctuality || []).map((row) => row.value),
          type: 'bar',
          color: divergingRamp()[4],
        },
      }
    }
    return {
      ...one,
      subtitle: __('Fullest hour of the day'),
      sparkline: {
        data: (answer.value.load_by_hour || []).map((row) => row.value),
        type: 'bar',
        color: occupancyInk(60),
      },
    }
  })
)

/** Zero is the timetable; five minutes is where late becomes reportable. */
const lateMarks = computed(() => [
  { value: 0, label: __('On the timetable') },
  { value: 300, label: __('Five minutes') },
])

/** Cool for early, neutral for on time, warm for late — the diverging ramp. */
const punctualityInks = computed(() => {
  const ramp = divergingRamp()
  return [ramp[1], ramp[4], ramp[7]]
})

/**
 * One bar, three segments — a share of a whole rather than three quantities.
 *
 * Three *series* and not three rows, because `seriesConfig` colours a series
 * and nothing colours a row: a bar chart of one series takes one colour for
 * every bar, and the ramp only means anything if each part takes its own step
 * of it. Stacked, so the eye reads the proportions and not three lengths it
 * has to add up.
 */
const punctualitySplit = computed(() => {
  const found = Object.fromEntries(punctuality.value.map((one) => [one.label, one.value]))
  if (!punctuality.value.length) return []
  return [{
    label: __('Readings'),
    early: found[__('Early')] || 0,
    on_time: found[__('On time')] || 0,
    late: found[__('Late')] || 0,
  }]
})

const punctualityConfig = computed(() => {
  const [cool, middle, warm] = punctualityInks.value
  return {
    early: { name: 'early', label: __('Early'), color: cool },
    on_time: { name: 'on_time', label: __('On time'), color: middle },
    late: { name: 'late', label: __('Late'), color: warm },
  }
})

/*
 * Not coloured per bar, and that was a decision rather than an omission.
 *
 * These bars are the lines, so colour following the entity would be right —
 * but a bar chart of one series takes one colour and frappe-ui has no per-row
 * colour prop. Going through `echartOptions` with a per-datapoint `itemStyle`
 * callback *does* colour them, and it also loses the series: the override is
 * deep-merged onto the built option and the merge takes the array with it, so
 * the plot comes back empty. A chart that draws nothing is worse than a chart
 * drawn in one colour, and one series in one colour is the honest default —
 * the identity is on the axis beside each bar, where a reader is already
 * looking.
 */

const lineOptions = computed(() => [
  { label: __('Every line'), value: '' },
  ...(answer.value.lines || []).map((one) => ({
    label: `${one.short_name} · ${one.line_name}`,
    value: one.name,
  })),
])

// Written out rather than generated: each one is a sentence somebody reads,
// and `__('{0} days')` interpolated over a list is a string a translator
// cannot make agree in a language with cases.
const rangeOptions = computed(() => [
  { label: __('Last 7 days'), value: '7' },
  { label: __('Last 30 days'), value: '30' },
  { label: __('Last 90 days'), value: '90' },
  { label: __('Last year'), value: '365' },
])

const window = computed(() =>
  answer.value.from ? __('{0} to {1}', [answer.value.from, answer.value.to]) : ''
)

async function pull() {
  loading.value = true
  try {
    answer.value = await network.rhythm({ line: line.value, days_back: range.value })
  } finally {
    loading.value = false
    ready.value = true
  }
}

// Watched rather than `@change`: frappe-ui's Select emits `update:modelValue`
// and `update:open`, and nothing else. A `@change` on it is a listener for an
// event that is never raised — the control moves, the model updates, and the
// server is never asked again.
watch([line, range], pull)

onMounted(pull)
</script>

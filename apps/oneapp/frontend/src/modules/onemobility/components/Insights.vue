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
  <div class="h-full min-h-body w-full overflow-y-auto" data-slot="insights">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <!-- What is being read, and over how long. One row, above everything. -->
      <div class="flex flex-wrap items-center gap-2" data-slot="insights-controls">
        <FacetBar
          v-model="facets"
          :facets="offered"
          :unavailable="unavailable"
        />
        <Select v-model="range" :options="rangeOptions" class="w-40" />
        <span v-if="window" class="ms-auto text-sm text-ink-muted">{{ window }}</span>
      </div>

      <EmptyState
        v-if="ready && !headline.length"
        icon="lucide-chart-column"
        :title="__('Nothing measured yet')"
        :description="__('Connect a source and let a day go by, and this fills in.')"
      />

      <template v-else>
        <!--
          Three tabs and not three screens, because they are three views of one
          set of readings and the facet bar above belongs to all of them. The
          split is by *subject* and not by chart type: an operator asking about
          the network, the fleet and the stops is asking three different
          questions, and each is answered off the tier rolled for it —
          `serviceHour`, `vehicleDay`, `stopHour`.
        -->
        <Tabs v-model="tab">
          <TabList variant="underline">
            <TabTrigger value="network" :label="__('The network')" icon-left="lucide-route" />
            <TabTrigger value="fleet" :label="__('The fleet')" icon-left="lucide-bus" />
            <TabTrigger value="stops" :label="__('The stops')" icon-left="lucide-map-pin" />
            <TabTrigger value="events" :label="__('The vehicles')" icon-left="lucide-door-open" />
          </TabList>

        <TabPanel value="network" class="flex flex-col gap-4 pt-4">
        <!--
          The four figures. Each carries the shape it is a summary of, because
          a number with its own history beside it answers "and is that
          unusual" without a second chart.
        -->
        <!-- A height, and it has to be here: a card with a trend across its
             bottom is taller than one with a number in it, and the grid gives
             every cell the height of the shortest unless told otherwise. -->
        <div
          class="grid auto-rows-tile grid-cols-2 gap-3 lg:grid-cols-4"
          data-slot="insights-headline"
        >
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

        <div class="h-80">
          <!--
            The one plot here that cannot be derived from any of the others,
            and the reason it earns its space: an average delay of ninety
            seconds is equally a service that is reliably a minute and a half
            late and one that is punctual four times in five and twenty minutes
            late on the fifth. Those are the same number and a different
            railway, and nothing else on this tab can tell them apart.

            Coloured across the diverging ramp rather than in one hue, because
            the buckets *are* the poles: early on one side, late on the other,
            on time in the neutral middle.
          -->
          <BarChart
            :data="spreadSplit"
            x="label"
            :y="spreadKeys"
            :title="__('How late, and how often')"
            :subtitle="__('Every reading, by how far it was from the timetable')"
            :series-config="spreadConfig"
            :loading="loading"
          />
        </div>
        </TabPanel>

        <TabPanel value="fleet" class="flex flex-col gap-4 pt-4">
          <EmptyState
            v-if="fleetReady && !fleet.reliability.length"
            icon="lucide-bus"
            :title="__('No vehicle has a history yet')"
            :description="__('The nightly roll-up writes one row per vehicle per day. It fills in after the first night.')"
          />
          <template v-else>
            <div class="h-96">
              <!--
                Ranked on the 85th percentile and not the mean. A vehicle that
                is punctual four days in five and twenty minutes late on the
                fifth averages the same as one four minutes late every day, and
                only one of them has something wrong with it.
              -->
              <BarChart
                :data="fleet.reliability"
                x="label"
                y="value"
                horizontal
                :title="__('Which vehicles run late')"
                :subtitle="__('Minutes behind the timetable on the worst one day in six')"
                :palette="[delayInk(240)]"
                :loading="loadingFleet"
              />
            </div>
            <div class="h-96">
              <!--
                One point per vehicle: how full it runs against how late it
                runs. The plot that answers the operator's own suspicion that a
                full bus is a late bus — which is usually wrong, because the
                cause is the road rather than the load, and a cloud with no
                slope in it says so faster than any number.
              -->
              <ScatterChart
                :data="fleet.load"
                x="x"
                y="y"
                :label="POINT_LABEL"
                :title="__('Does a full bus run late?')"
                :subtitle="__('Each vehicle: average load across, average lateness up')"
                :palette="[occupancyInk(60)]"
                :loading="loadingFleet"
              />
            </div>
          </template>
        </TabPanel>

        <TabPanel value="stops" class="flex flex-col gap-4 pt-4">
          <EmptyState
            v-if="stopsReady && !stopped.busiest.length"
            icon="lucide-map-pin"
            :title="__('No stop has been visited yet')"
            :description="__('Stop visits are worked out from positions overnight. They appear after the first pass.')"
          />
          <template v-else>
            <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div class="h-96">
                <BarChart
                  :data="stopped.busiest"
                  x="label"
                  y="value"
                  horizontal
                  :title="__('Where the service goes')"
                  :subtitle="__('Vehicle visits, worked out from positions')"
                  :palette="[occupancyInk(20)]"
                  :loading="loadingStops"
                />
              </div>
              <div class="h-96">
                <!--
                  The number worth the whole table. A ten minute timetable run
                  as a pair four minutes apart and then a sixteen minute hole is
                  on time by every average on the first tab, and unusable to the
                  person standing at the stop. This is the gap between the wait
                  most people get and the wait the timetable implies.
                -->
                <BarChart
                  :data="stopped.bunching"
                  x="label"
                  y="value"
                  horizontal
                  :title="__('Where the wait is worse than the timetable')"
                  :subtitle="__('Extra minutes at the stop, on the worst one wait in six')"
                  :palette="[delayInk(300)]"
                  :loading="loadingStops"
                />
              </div>
            </div>
            <div class="h-72">
              <AreaChart
                :data="stopped.by_hour"
                x="label"
                y="value"
                :title="__('Visits through the day')"
                :subtitle="__('Every stop together, by hour')"
                :palette="[occupancyInk(45)]"
                :loading="loadingStops"
              />
            </div>
          </template>
        </TabPanel>

        <!--
          What the vehicles said about themselves. A fourth subject rather
          than a fourth chart type, like the three above it: those answer
          "how did the service run", this answers "how did the equipment
          behave", and the two have different audiences on the same morning.

          The attention list is first and is not a chart, because it is the
          only thing on this screen about *now*. Everything else here is a
          fortnight rolled up; a door that is jammed at this minute belongs
          above all of it or not on the page at all.
        -->
        <TabPanel value="events" class="flex flex-col gap-4 pt-4">
          <EmptyState
            v-if="eventsReady && !behaviour.kinds.length"
            icon="lucide-door-open"
            :title="__('No vehicle has reported yet')"
            :description="__('Door states, faults and trip states arrive from a bridge on the vehicle.')"
          />
          <template v-else>
            <!-- Still in force, oldest first. A fault that was fixed has a
                 later state and is gone from here without anybody closing
                 it. -->
            <Panel tone="red" pad="tight" v-if="trouble.rows.length" data-slot="attention" class="flex flex-col gap-1">
              <p class="text-p-sm font-medium text-ink-primary">
                {{ __('{0} on {1} vehicles, right now', [troubleWord, trouble.vehicles]) }}
              </p>
              <div
                v-for="one in trouble.rows"
                :key="one.vehicle + one.kind + one.part"
                data-slot="attention-row"
                class="flex flex-wrap items-baseline gap-x-2 text-p-xs"
              >
                <span class="font-medium text-ink-primary">{{ one.vehicle }}</span>
                <span class="text-ink-secondary">{{ one.value }}</span>
                <span v-if="one.part" class="text-ink-muted">{{ __('part {0}', [one.part]) }}</span>
                <span class="text-ink-muted">{{ __('for {0} min', [one.minutes]) }}</span>
                <span class="ms-auto font-mono text-ink-gray-4">{{ one.part_of }}</span>
              </div>
            </Panel>

            <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
              <div class="h-96">
                <!--
                  Two lines, deliberately. The measured dwell is the doors;
                  the inferred one is how long the vehicle sat inside a
                  stop's radius. Drawing only the measured one on a fleet
                  that half-reports would silently answer for half the
                  network, and drawing only the inferred one is what this
                  arc exists to improve on.
                -->
                <LineChart
                  :data="dwell"
                  x="label"
                  :y="['measured', 'inferred']"
                  :title="__('How long the doors are open')"
                  :subtitle="__('Median seconds by hour')"
                  :series-config="dwellConfig"
                  :loading="loadingEvents"
                />
              </div>
              <div class="h-96">
                <BarChart
                  :data="behaviour.hours"
                  x="label"
                  y="events"
                  :title="__('What the vehicles report, by hour')"
                  :subtitle="__('Every state change, all kinds together')"
                  :palette="[occupancyInk(45)]"
                  :loading="loadingEvents"
                />
              </div>
            </div>

            <!-- What is actually being reported, and which VDV part it came
                 from. A count nobody can attribute is a count nobody can
                 check against their own supplier. -->
            <div class="flex flex-col gap-1" data-slot="event-kinds">
              <div
                v-for="one in behaviour.kinds"
                :key="one.kind"
                class="flex flex-wrap items-baseline gap-x-2 border-b border-outline-gray-1 py-1 text-p-xs"
              >
                <span class="font-medium text-ink-primary">{{ one.kind }}</span>
                <span class="text-ink-muted">{{ __('{0} reports', [one.events]) }}</span>
                <span v-if="one.trouble" class="text-ink-red-3">
                  {{ __('{0} needing attention', [one.trouble]) }}
                </span>
                <span class="ms-auto font-mono text-ink-gray-4">{{ one.part_of }}</span>
              </div>
            </div>
          </template>
        </TabPanel>
        </Tabs>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  AreaChart, BarChart, HeatmapChart, LineChart, NumberCard, ScatterChart,
  Select, TabList, TabPanel, TabTrigger, Tabs,
} from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { delayInk, divergingRamp, occupancyInk } from '@/modules/onemobility/lib/palette'
import FacetBar from '@/modules/onemobility/components/FacetBar.vue'
import Panel from '@/shared/components/Panel.vue'

defineProps({
  /** The resolved screen. Unused: this surface reads no records. */
  spec: { type: Object, default: () => ({}) },
})

/**
 * Which key on a scatter row carries the point's name. Bound rather than
 * written as a literal attribute: `label="label"` is a column name and reads
 * to the i18n guard as a word somebody forgot to translate, which is a fair
 * thing for it to think.
 */
const POINT_LABEL = 'label'

/**
 * Which tab can answer for a kind of thing, so a record arriving from Lines,
 * Stops or Vehicles lands on the tier that knows about it rather than on the
 * network tab with its own chip greyed out.
 */
const HOME_TAB = { vehicle: 'fleet', stop: 'stops' }

const tab = ref('network')
const range = ref('30')
const ready = ref(false)
const loading = ref(true)
const answer = ref({})

/**
 * What is narrowing every tab. One object, shared — the point of the facet bar
 * is that a line chosen while looking at the network is still chosen when the
 * fleet tab opens, because it is the same question asked of a different table.
 */
const facets = ref({})
const offered = ref([])

const loadingFleet = ref(false)
const fleetReady = ref(false)
const fleetAnswer = ref({})

const loadingStops = ref(false)
const stopsReady = ref(false)
const stopsAnswer = ref({})

const loadingEvents = ref(false)
const eventsReady = ref(false)
const eventsAnswer = ref({})
const doorsAnswer = ref({})
const troubleAnswer = ref({})

const spread = computed(() => answer.value.spread || [])

const fleet = computed(() => ({
  reliability: fleetAnswer.value.reliability || [],
  load: fleetAnswer.value.load || [],
}))

const stopped = computed(() => ({
  busiest: stopsAnswer.value.busiest || [],
  bunching: stopsAnswer.value.bunching || [],
  by_hour: stopsAnswer.value.by_hour || [],
}))

const trouble = computed(() => ({
  rows: troubleAnswer.value.rows || [],
  vehicles: troubleAnswer.value.vehicles || 0,
}))

const troubleWord = computed(() =>
  trouble.value.rows.length === 1
    ? __('One thing needs attention')
    : __('{0} things need attention', [trouble.value.rows.length]),
)

const behaviour = computed(() => ({
  kinds: eventsAnswer.value.kinds || [],
  hours: (eventsAnswer.value.hours || []).map((one) => ({
    label: `${String(one.hour).padStart(2, '0')}:00`,
    // Every kind together: the per-kind split is the list underneath, and a
    // stacked bar of ten thousand door events beside one fault is a chart
    // where the fault is invisible.
    events: Object.entries(one).reduce(
      (total, [key, value]) => (key === 'hour' ? total : total + value),
      0,
    ),
  })),
}))

/**
 * The two dwell series on one x axis.
 *
 * Joined by hour here rather than on the server because they come off two
 * different tiers, and an hour present in one and missing from the other is a
 * real answer — a fleet that reports doors only in the morning should show a
 * line that stops, not one interpolated across the gap.
 */
const dwell = computed(() => {
  const measured = new Map((doorsAnswer.value.measured || []).map((one) => [one.hour, one.p50]))
  const inferred = new Map((doorsAnswer.value.inferred || []).map((one) => [one.hour, one.p50]))
  const hours = [...new Set([...measured.keys(), ...inferred.keys()])].sort((a, b) => a - b)
  return hours.map((hour) => ({
    label: `${String(hour).padStart(2, '0')}:00`,
    measured: measured.get(hour) ?? null,
    inferred: inferred.get(hour) ?? null,
  }))
})

/**
 * And what each line is, spelled out.
 *
 * Two series with no legend is a chart nobody can read, and here the two are
 * the whole point: one is the doors and one is how long the vehicle sat
 * inside a stop's radius. They disagree by a factor of three on the fixture,
 * which is the argument for having built the measured one.
 */
const dwellConfig = computed(() => ({
  measured: {
    name: 'measured',
    label: __('At the doors'),
    color: occupancyInk(70),
  },
  inferred: {
    name: 'inferred',
    label: __('From positions'),
    color: occupancyInk(25),
  },
}))

/**
 * Which facets the tab in front cannot honour, straight from the server that
 * knows — `serviceHour` has no vehicle column, `vehicleDay` no stop. Read off
 * the answer rather than hard-coded here, so a column added to a fact table
 * turns a chip back on without a line changing in the browser.
 */
const unavailable = computed(() => {
  if (tab.value === 'fleet') return fleetAnswer.value.unavailable || []
  if (tab.value === 'stops') return stopsAnswer.value.unavailable || []
  return answer.value.unavailable || []
})

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
    label: __('Every reading'),
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

/**
 * The distribution's own colours, one series per bucket so each takes its step
 * of the diverging ramp — cool at the early end, neutral through the on-time
 * bucket, warm and warmer out into the tail. `seriesConfig` keyed by label is
 * how a bar chart of one series is given more than one colour; see the note
 * below for what happens when you reach for `echartOptions` instead.
 */
/**
 * The buckets as *series* rather than rows, for the reason spelled out under
 * the line ranking below: `seriesConfig` colours a series and nothing colours a
 * row, so seven bars of one series take one colour however the config is keyed.
 * Seven series over one category draws the same seven bars side by side, each
 * its own step of the ramp, and gets a legend naming them for free.
 *
 * Keyed `b0`…`b6` and not by the label, because the label is translated and a
 * series key that changes with the interface language is a chart that loses its
 * colours in German.
 */
const spreadKeys = computed(() => spread.value.map((_one, at) => `b${at}`))

const spreadSplit = computed(() => {
  if (!spread.value.length) return []
  const row = { label: __('Every reading') }
  spread.value.forEach((one, at) => {
    row[`b${at}`] = one.value
  })
  return [row]
})

const spreadConfig = computed(() => {
  const ramp = divergingRamp()
  // Seven buckets across nine ramp steps, skipping the two that sit closest to
  // the neutral middle on either side — they read as the same colour at bar
  // size, and a legend with two indistinguishable swatches is worse than one
  // with a slightly coarser scale.
  const steps = [ramp[0], ramp[2], ramp[4], ramp[5], ramp[6], ramp[7], ramp[8]]
  return Object.fromEntries(
    spread.value.map((one, at) => [
      `b${at}`,
      { name: `b${at}`, label: one.label, color: steps[at] || steps[steps.length - 1] },
    ])
  )
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

/** The facets, as the server's endpoints want them: one JSON object. */
const narrowed = computed(() => ({
  facets: JSON.stringify(facets.value),
  days_back: range.value,
}))

async function pull() {
  loading.value = true
  try {
    answer.value = await network.rhythm(narrowed.value)
  } finally {
    loading.value = false
    ready.value = true
  }
}

async function pullFleet() {
  loadingFleet.value = true
  try {
    fleetAnswer.value = await network.fleet(narrowed.value)
  } finally {
    loadingFleet.value = false
    fleetReady.value = true
  }
}

async function pullEvents() {
  loadingEvents.value = true
  try {
    // Three at once. They read three tiers and need nothing from each other,
    // and asking serially spends two round trips drawing a frame with
    // nothing in it — the same argument `onMounted` already makes below.
    const [shape, spans, wrong] = await Promise.all([
      network.behaviour(narrowed.value),
      network.doorTimes(narrowed.value),
      network.attention(),
    ])
    eventsAnswer.value = shape
    doorsAnswer.value = spans
    troubleAnswer.value = wrong
  } finally {
    loadingEvents.value = false
    eventsReady.value = true
  }
}

async function pullStops() {
  loadingStops.value = true
  try {
    stopsAnswer.value = await network.stops(narrowed.value)
  } finally {
    loadingStops.value = false
    stopsReady.value = true
  }
}

/**
 * The tab in front, and only it.
 *
 * Three tabs asking three questions on mount would be three aggregate queries
 * for two answers nobody has looked at — and the fleet and stop tiers are the
 * two with a row per vehicle and per stop behind them. Each tab fetches when
 * it is first opened and again when the facets or the window move under it.
 */
function pullCurrent() {
  if (tab.value === 'fleet') return pullFleet()
  if (tab.value === 'stops') return pullStops()
  return pull()
}

// Watched rather than `@change`: frappe-ui's Select emits `update:modelValue`
// and `update:open`, and nothing else. A `@change` on it is a listener for an
// event that is never raised — the control moves, the model updates, and the
// server is never asked again.
watch([facets, range], () => {
  // The tab in front is refetched now; the other two are marked unfetched, so
  // opening one asks again rather than showing the previous window's numbers
  // under the new window's heading.
  if (tab.value !== 'fleet') fleetReady.value = false
  if (tab.value !== 'stops') stopsReady.value = false
  if (tab.value !== 'events') eventsReady.value = false
  writeTheUrl()
  pullCurrent()
}, { deep: true })

watch(tab, () => {
  if (tab.value === 'fleet' && !fleetReady.value) pullFleet()
  if (tab.value === 'stops' && !stopsReady.value) pullStops()
  if (tab.value === 'events' && !eventsReady.value) pullEvents()
})

const route = useRoute()
const router = useRouter()

/**
 * The facets live in the URL as well as in the ref, and both directions matter.
 *
 * Inwards: `actions.py` puts a "How this line ran" button on a Line, and the
 * engine's screen-action carries the record's name over as one query parameter
 * — so a record hands its identity to the screen that can say how it behaved,
 * without either half knowing anything about the other beyond the name of a
 * facet.
 *
 * Outwards: a narrowed view is then a link somebody can send. "Look at U6's
 * punctuality" being a URL rather than a set of instructions is most of what
 * makes a screen like this get used by more than the person who built it.
 */
function readTheUrl() {
  const found = {}
  for (const one of offered.value) {
    const value = route.query[one.key]
    if (value) found[one.key] = String(value)
  }
  facets.value = found

  // Opened *at* something, so open where that something can be seen. Only on
  // arrival: after that the tab is the reader's to choose.
  for (const key of Object.keys(found)) {
    if (HOME_TAB[key]) {
      tab.value = HOME_TAB[key]
      break
    }
  }
}

function writeTheUrl() {
  const query = { ...route.query }
  for (const one of offered.value) delete query[one.key]
  router.replace({ query: { ...query, ...facets.value } }).catch(() => {})
}

onMounted(async () => {
  // Together, not one after the other. The vocabulary and the numbers do not
  // need each other — `resolve` runs on the server against whatever facets the
  // URL carried, and the bar is drawn from the vocabulary — so asking serially
  // spent a whole round trip putting the frame on screen with nothing in it.
  const [choices] = await Promise.all([network.offered(), pull()])
  offered.value = choices.facets || []
  readTheUrl()

  // Only if the URL actually narrowed something, or moved the tab: the first
  // fetch above already answered the unnarrowed question.
  if (Object.keys(facets.value).length || tab.value !== 'network') pullCurrent()
})
</script>

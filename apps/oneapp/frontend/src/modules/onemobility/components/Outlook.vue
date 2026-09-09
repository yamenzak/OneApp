<template>
  <!--
    The same aggregate tier as Insights, read about a day that may not have
    happened yet.

    Insights answers *what did this network do*. This answers *what is it going
    to do, and how sure is that* — and the two are one lookup, because what a
    Tuesday at nine looks like is every Tuesday at nine there has been. Whether
    the Tuesday being asked about is next week changes the label and nothing
    about the arithmetic. See `onemobility/forecast.py`.

    **Every number on this screen is drawn with its spread**, and that is the
    rule the screen exists to keep rather than a decoration on it. The lateness
    plot is three lines and not one, the risk list is a probability and not a
    mean, and anything resting on too little history says so instead of looking
    like the rest. A confident wrong forecast costs more trust than no forecast,
    and an operator who catches this screen being certain and wrong once will
    never use it again.
  -->
  <div class="h-full min-h-[28rem] w-full overflow-y-auto" data-slot="outlook">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <div class="flex flex-wrap items-center gap-2" data-slot="outlook-controls">
        <FacetBar v-model="facets" :facets="offered" :unavailable="unavailable" />
        <Select v-model="day" :options="dayOptions" class="w-44" />
        <Select v-model="hour" :options="hourOptions" class="w-32" />
        <Badge
          v-if="ready && learning"
          theme="amber"
          variant="subtle"
          :label="__('Still learning')"
          data-slot="outlook-learning"
        />
        <span v-if="basisLine" class="ms-auto text-sm text-ink-gray-5">{{ basisLine }}</span>
      </div>

      <EmptyState
        v-if="ready && !hours.length"
        icon="lucide-chart-line"
        :title="__('Nothing to go on yet')"
        :description="__('This reads the nightly roll-up. Once a few days of positions are in, it can say what a Tuesday looks like.')"
      />

      <template v-else>
        <div
          class="grid auto-rows-[7.5rem] grid-cols-2 gap-3 lg:grid-cols-4"
          data-slot="outlook-headline"
        >
          <NumberCard
            v-for="one in headline"
            :key="one.title"
            :title="one.title"
            :value="one.value ?? 0"
            :suffix="one.suffix"
            :subtitle="one.subtitle"
            :sparkline="one.sparkline"
            :loading="loading"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-80">
            <!--
              Three lines and not one, and that is the whole argument for
              storing percentiles. The middle line is what an ETA should say,
              the top is what a timetable should be built from, and the distance
              between them is the thing a single averaged line hides: a service
              that is reliably two minutes late and one that is punctual four
              times in five draw the same average and are not the same railway.
            -->
            <LineChart
              :data="byHour"
              x="label"
              :y="['p50', 'p85', 'p95']"
              :title="__('How late it is likely to run')"
              :subtitle="__('Seconds behind the timetable, as a range')"
              :series-config="spreadConfig"
              :reference-lines="lateMarks"
              :loading="loading"
            />
          </div>
          <div class="h-80">
            <!--
              The same distribution said as a probability, which is the form an
              operator acts on: nobody holds a bus because the mean is 240
              seconds, and somebody does because two runs in three will miss the
              five-minute mark.
            -->
            <BarChart
              :data="byHour"
              x="label"
              y="late_chance"
              :title="__('Chance of running late')"
              :subtitle="__('Percent of runs past five minutes, hour by hour')"
              :palette="[delayInk(300)]"
              :loading="loading"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-96">
            <!--
              Worst first, because this is a list somebody reads the top of.
              Ordered by line name it would be a reference table; ordered by
              risk it is a shift plan.
            -->
            <BarChart
              :data="atRisk"
              x="label"
              y="chance"
              horizontal
              :title="__('Which line to watch')"
              :subtitle="riskSubtitle"
              :palette="[delayInk(300)]"
              :loading="loadingRisk"
            />
          </div>

          <div
            class="flex flex-col gap-2 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4"
            data-slot="outlook-unusual"
          >
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-base font-medium text-ink-gray-8">{{ __('Not like itself') }}</p>
              <span class="text-xs text-ink-gray-5">{{ __('Today against its own history') }}</span>
            </div>
            <!--
              A z-score and not a threshold, which is the only version of this
              that works: "alert over ten minutes late" fires all day on a line
              that is always ten minutes late, and never fires on the one that
              has never been late until this morning.
            -->
            <p v-if="unusualReady && !findings.length" class="py-6 text-center text-sm text-ink-gray-5">
              {{ __('Everything is running the way it usually does.') }}
            </p>
            <ul v-else class="flex flex-col gap-1.5 overflow-y-auto">
              <li
                v-for="one in findings"
                :key="`${one.line}-${one.hour}`"
                class="flex items-center gap-2 rounded-6 px-2 py-1.5 hover:bg-surface-gray-2"
              >
                <Badge
                  :theme="one.worse ? 'red' : 'green'"
                  variant="subtle"
                  :label="one.worse ? __('Worse') : __('Better')"
                />
                <span class="truncate text-sm text-ink-gray-8">{{ one.line }}</span>
                <span class="text-xs tabular-nums text-ink-gray-5">{{ one.label }}</span>
                <span class="ms-auto shrink-0 text-xs tabular-nums text-ink-gray-6">
                  {{ minutes(one.delay_avg) }} · {{ __('usually {0}', [minutes(one.usual_p50)]) }}
                </span>
              </li>
            </ul>
          </div>
        </div>

        <!--
          Only when a stop has been chosen, because that is the only time there
          is one to answer about. The facet bar is already the way a screen here
          is narrowed to a stop, so this needs no picker of its own — and a
          panel that appeared with an empty control in it would be a question
          asked of a reader who had not asked one.
        -->
        <div
          v-if="facets.stop"
          class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-elevation-2 p-4"
          data-slot="outlook-stop"
        >
          <div class="flex items-baseline justify-between gap-2">
            <p class="text-base font-medium text-ink-gray-8">{{ __('At this stop') }}</p>
            <span class="text-xs text-ink-gray-5">
              {{ __('{0} on a {1}', [hourLabel, weekdayName]) }}
            </span>
          </div>
          <p v-if="stopAnswer.scheduled_only" class="text-sm text-ink-gray-5">
            {{ __('Nothing has been seen at this stop in this hour yet, so there is no history to read. Until there is, an arrival here is the timetable and the delay the vehicle is already carrying.') }}
          </p>
          <div v-else class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div v-for="one in stopFigures" :key="one.title" class="flex flex-col gap-0.5">
              <p class="text-xs text-ink-gray-5">{{ one.title }}</p>
              <p class="text-xl font-medium tabular-nums text-ink-gray-8">{{ one.value }}</p>
              <p class="text-xs text-ink-gray-5">{{ one.note }}</p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { Badge, BarChart, LineChart, NumberCard, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { delayInk, divergingRamp, occupancyInk } from '@/modules/onemobility/lib/palette'
import FacetBar from '@/modules/onemobility/components/FacetBar.vue'

defineProps({
  /** The resolved screen. Unused: this surface reads no records. */
  spec: { type: Object, default: () => ({}) },
})

/**
 * How far ahead the day picker offers, matching `forecast.HORIZON_DAYS`. Past
 * that the server refuses, and a control that offers a choice the server will
 * not honour is a control that teaches people not to trust it.
 */
const AHEAD = 14

/** Monday first, as `insights.py` and `live.record` both count it. */
const WEEKDAYS = () => [
  __('Monday'), __('Tuesday'), __('Wednesday'), __('Thursday'),
  __('Friday'), __('Saturday'), __('Sunday'),
]

const facets = ref({})
const offered = ref([])
const day = ref(today())
const hour = ref('8')

const loading = ref(true)
const ready = ref(false)
const answer = ref({})

const loadingRisk = ref(false)
const riskAnswer = ref({})

const unusualReady = ref(false)
const unusualAnswer = ref({})

const stopAnswer = ref({})

function today() {
  return new Date().toISOString().slice(0, 10)
}

function iso(offset) {
  const at = new Date()
  at.setDate(at.getDate() + offset)
  return at.toISOString().slice(0, 10)
}

/** Seconds as a person says them. Minutes once it is minutes, seconds below. */
function minutes(seconds) {
  if (seconds === null || seconds === undefined) return '—'
  const value = Number(seconds)
  if (Math.abs(value) < 60) return __('{0}s', [Math.round(value)])
  return __('{0} min', [(value / 60).toFixed(1)])
}

const hours = computed(() => answer.value.hours || [])
const unavailable = computed(() => answer.value.unavailable || [])
const learning = computed(() => Boolean(answer.value.learning))
const findings = computed(() => unusualAnswer.value.findings || [])

const byHour = computed(() =>
  hours.value.map((one) => ({
    label: one.label,
    p50: one.delay?.p50 ?? 0,
    p85: one.delay?.p85 ?? 0,
    p95: one.delay?.p95 ?? 0,
    late_chance: one.late_chance ?? 0,
  }))
)

const atRisk = computed(() =>
  (riskAnswer.value.lines || [])
    .filter((one) => one.chance !== null)
    .slice(0, 12)
    .map((one) => ({ label: one.line, chance: one.chance }))
)

/**
 * The day the picker is on, and how far off it is. Written as its own line
 * rather than folded into the option labels: "Tuesday, in 3 days" is what
 * somebody needs to read back after choosing, and an option list they have
 * closed cannot tell them.
 */
const chosenDay = computed(() => new Date(`${day.value}T00:00:00`))
const weekdayName = computed(() => {
  // JavaScript counts Sunday as nought and a service week does not.
  const at = (chosenDay.value.getDay() + 6) % 7
  return WEEKDAYS()[at] || ''
})
const hourLabel = computed(() => `${String(Number(hour.value)).padStart(2, '0')}:00`)

const dayOptions = computed(() => {
  const out = [{ label: __('Today'), value: today() }, { label: __('Tomorrow'), value: iso(1) }]
  for (let ahead = 2; ahead <= AHEAD; ahead += 1) {
    const at = new Date()
    at.setDate(at.getDate() + ahead)
    out.push({
      label: __('{0}, in {1} days', [WEEKDAYS()[(at.getDay() + 6) % 7], ahead]),
      value: iso(ahead),
    })
  }
  return out
})

const hourOptions = computed(() =>
  Array.from({ length: 24 }, (_one, at) => ({
    label: `${String(at).padStart(2, '0')}:00`,
    value: String(at),
  }))
)

const basisLine = computed(() => {
  const total = hours.value.reduce((sum, one) => sum + (one.basis || 0), 0)
  if (!total) return ''
  return __('{0} readings, {1} to {2}', [total, answer.value.from, answer.value.to])
})

const riskSubtitle = computed(() =>
  __('Chance of passing five minutes late at {0}', [hourLabel.value])
)

/** Zero is the timetable; five minutes is where late becomes reportable. */
const lateMarks = computed(() => [
  { value: 0, label: __('On the timetable') },
  { value: 300, label: __('Five minutes') },
])

/**
 * Three steps of the diverging ramp, warmer as the percentile rises — so the
 * outer line reads as the worse case without a legend having to say it.
 */
const spreadConfig = computed(() => {
  const ramp = divergingRamp()
  return {
    p50: { name: 'p50', label: __('Half the runs'), color: ramp[5] },
    p85: { name: 'p85', label: __('Most runs'), color: ramp[6] },
    p95: { name: 'p95', label: __('Nearly all runs'), color: ramp[8] },
  }
})

const peak = computed(() => {
  let worst = null
  for (const one of hours.value) {
    if (one.delay?.p85 === null || one.delay?.p85 === undefined) continue
    if (!worst || one.delay.p85 > worst.delay.p85) worst = one
  }
  return worst
})

const busiest = computed(() => {
  let most = null
  for (const one of hours.value) {
    if (one.occupancy?.p85 === null || one.occupancy?.p85 === undefined) continue
    if (!most || one.occupancy.p85 > most.occupancy.p85) most = one
  }
  return most
})

const headline = computed(() => [
  {
    title: __('Worst hour'),
    value: peak.value ? Math.round((peak.value.delay.p85 || 0) / 60) : 0,
    suffix: __(' min'),
    subtitle: peak.value ? __('at {0}, most runs under this', [peak.value.label]) : '',
    sparkline: { data: byHour.value.map((one) => one.p85), type: 'line', color: delayInk(300) },
  },
  {
    title: __('Chance of late'),
    value: peak.value ? Math.round(peak.value.late_chance || 0) : 0,
    suffix: '%',
    subtitle: peak.value ? __('at {0}', [peak.value.label]) : '',
    sparkline: { data: byHour.value.map((one) => one.late_chance), type: 'bar' },
  },
  {
    title: __('Fullest hour'),
    value: busiest.value ? Math.round(busiest.value.occupancy.p85 || 0) : 0,
    suffix: '%',
    subtitle: busiest.value ? __('at {0}, most runs under this', [busiest.value.label]) : '',
    sparkline: {
      data: hours.value.map((one) => one.occupancy?.p85 ?? 0),
      type: 'bar',
      color: occupancyInk(60),
    },
  },
  {
    // Not a measure of the network — a measure of how much this screen knows,
    // which is the number every other card on it depends on.
    title: __('Hours with a history'),
    value: hours.value.filter((one) => !one.learning).length,
    suffix: __(' of {0}', [hours.value.length || 0]),
    subtitle: __('The rest are still learning'),
    sparkline: { data: hours.value.map((one) => one.basis || 0), type: 'bar' },
  },
])

const stopFigures = computed(() => {
  const one = stopAnswer.value
  if (!one || one.scheduled_only) return []
  return [
    {
      title: __('Usually arrives'),
      value: minutes(one.early_s),
      note: __('behind the timetable'),
    },
    {
      title: __('Plan for'),
      value: minutes(one.likely_s),
      note: __('most runs are inside this'),
    },
    {
      title: __('Wait between vehicles'),
      value: minutes(one.headway_p85_s),
      note: __('what the longest waits look like'),
    },
    {
      title: __('Time at the stop'),
      value: minutes(one.dwell_avg_s),
      note: __('from {0} visits', [one.basis || 0]),
    },
  ]
})

/** What every endpoint here is narrowed by. One object, one place. */
const narrowed = computed(() => ({
  facets: JSON.stringify(facets.value),
  when: `${day.value} ${String(Number(hour.value)).padStart(2, '0')}:00:00`,
}))

async function pull() {
  loading.value = true
  try {
    answer.value = await network.outlook({ facets: narrowed.value.facets, when: day.value })
  } finally {
    loading.value = false
    ready.value = true
  }
}

async function pullRisk() {
  loadingRisk.value = true
  try {
    riskAnswer.value = await network.risk(narrowed.value)
  } finally {
    loadingRisk.value = false
  }
}

async function pullUnusual() {
  try {
    unusualAnswer.value = await network.unusual({ facets: narrowed.value.facets })
  } finally {
    unusualReady.value = true
  }
}

async function pullStop() {
  if (!facets.value.stop) {
    stopAnswer.value = {}
    return
  }
  stopAnswer.value = await network.expect({
    stop: facets.value.stop,
    line: facets.value.line || '',
    when: narrowed.value.when,
  })
}

/**
 * The day moves three of the four reads and not the fourth: `unusual` is about
 * today by definition — a day that has not happened cannot be behaving oddly —
 * so it is fetched once and left alone while somebody scrubs through next week.
 */
watch([facets, day], () => {
  pull()
  pullRisk()
  pullStop()
})
watch(hour, () => {
  pullRisk()
  pullStop()
})

onMounted(async () => {
  offered.value = (await network.offered()).facets || []
  pull()
  pullRisk()
  pullUnusual()
})
</script>

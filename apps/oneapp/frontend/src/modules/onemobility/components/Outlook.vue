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
  <div class="h-full min-h-body w-full overflow-y-auto" data-slot="outlook">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <div class="flex flex-wrap items-center gap-2" data-slot="outlook-controls">
        <Narrow v-model="facets" :fields="offered" :unavailable="unavailable" :measure="false" />
        <Select v-model="day" :options="dayOptions" class="w-44" />
        <Select v-model="hour" :options="hourOptions" class="w-32" />
        <Badge
          v-if="ready && learning"
          theme="amber"
          variant="subtle"
          :label="__('Still learning')"
          data-slot="outlook-learning"
        />
        <span v-if="basisLine" class="ms-auto text-sm text-ink-muted">{{ basisLine }}</span>
      </div>

      <EmptyState
        v-if="ready && !hours.length"
        icon="lucide-chart-line"
        :title="__('Nothing to go on yet')"
        :description="__('From the nightly roll-up. A few days of positions and it can say what a Tuesday looks like.')"
      />

      <template v-else>
        <div
          class="grid auto-rows-tile grid-cols-2 gap-3 lg:grid-cols-4"
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
          <div class="h-80">
            <!--
              The same arithmetic on the other measure, and the reason the
              occupancy percentiles exist: "half full on average" is a number,
              "full on three journeys in ten at this hour" is a decision about
              whether to put another vehicle out.
            -->
            <BarChart
              :data="byHour"
              x="label"
              y="full_chance"
              :title="__('Chance of being full')"
              :subtitle="__('Percent of journeys over four fifths loaded')"
              :palette="[occupancyInk(85)]"
              :loading="loading"
            />
          </div>

          <div class="h-80">
            <!--
              Where the gap collapses, which is a different question from
              which vehicles have caught each other right now — that one is on
              the map and is radioed about; this one is fixed in a timetable.
            -->
            <BarChart
              :data="bunches"
              x="label"
              y="chance"
              horizontal
              :title="__('Where the gap collapses')"
              :subtitle="bunchingSubtitle"
              :palette="[occupancyInk(45)]"
              :loading="loadingBunching"
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

          <Panel ground="raised" class="flex flex-col gap-2" data-slot="outlook-unusual">
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-base font-medium text-ink-primary">{{ __('Not like itself') }}</p>
              <span class="text-xs text-ink-muted">{{ __('Today against its own history') }}</span>
            </div>
            <!--
              A z-score and not a threshold, which is the only version of this
              that works: "alert over ten minutes late" fires all day on a line
              that is always ten minutes late, and never fires on the one that
              has never been late until this morning.
            -->
            <p v-if="unusualReady && !findings.length" class="py-6 text-center text-sm text-ink-muted">
              {{ __('Everything is running the way it usually does.') }}
            </p>
            <ul v-else class="flex flex-col gap-1.5 overflow-y-auto">
              <Row
                v-for="one in findings"
                :key="`${one.line}-${one.hour}`"
                as="li"
                edge="rounded"
                pad="tight"
              >
                <template #lead>
                  <Badge
                    :theme="one.worse ? 'red' : 'green'"
                    variant="subtle"
                    :label="one.worse ? __('Worse') : __('Better')"
                  />
                </template>
                <span class="flex items-center gap-2">
                  <span class="truncate text-sm text-ink-primary">{{ one.line }}</span>
                  <span class="text-xs tabular-nums text-ink-muted">{{ one.label }}</span>
                </span>
                <template #trail>
                  <span class="text-xs tabular-nums text-ink-secondary">
                    {{ minutes(one.delay_avg) }} · {{ __('usually {0}', [minutes(one.usual_p50)]) }}
                  </span>
                </template>
              </Row>
            </ul>
          </Panel>
        </div>

        <!--
          The same day read off the event tier rather than the position tier.
          Everything above forecasts how the *service* runs; this forecasts how
          the *equipment* behaves, and an operator planning a shift needs both —
          a Tuesday that is reliably late at eight and a Tuesday on which a door
          reliably jams at eight are two different people's problem.

          Drawn only where there is something to draw. A workspace with no
          bridge on any vehicle has no event tier, and an empty chart captioned
          "no faults" would be read as good news rather than as no data.
        -->
        <div v-if="faultHours.length" class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-80">
            <!--
              A counted frequency, not a normal tail — see `forecast.faults`.
              Four Tuesdays out of thirteen is a number somebody can check
              against their own memory of those four Tuesdays, which is not
              true of a probability derived from two stored percentiles.
            -->
            <BarChart
              :data="faultHours"
              x="label"
              y="chance"
              :title="__('When things break')"
              :subtitle="faultSubtitle"
              :palette="[troubleInk()]"
              :loading="loadingFaults"
            />
          </div>

          <Panel ground="raised" class="flex flex-col gap-4" data-slot="outlook-faults">
            <div class="flex flex-col gap-0.5">
              <p class="text-base font-medium text-ink-primary">
                {{ __('What a {0} usually costs', [weekdayName]) }}
              </p>
              <p class="text-xs text-ink-muted">{{ faultBasis }}</p>
            </div>
            <!-- Three across on anything but a phone, so they read as one
                 answer in three parts rather than as a wrapped list. -->
            <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div v-for="one in faultFigures" :key="one.title" class="flex flex-col gap-0.5">
                <p class="text-xs text-ink-muted">{{ one.title }}</p>
                <p class="text-xl font-medium tabular-nums text-ink-primary">{{ one.value }}</p>
                <p class="text-xs text-ink-muted">{{ one.note }}</p>
              </div>
            </div>
          </Panel>
        </div>

        <!--
          Whether any of the above has been worth reading, off the record the
          nightly job wrote before the answer existed. Last on the screen and
          not first, because it is the question somebody asks after they have
          looked at a forecast rather than before — but it is on the same screen
          deliberately: a scorecard filed somewhere else is a scorecard nobody
          checks against the thing it scores.
        -->
        <Panel ground="raised" class="flex flex-wrap items-center gap-3" data-slot="outlook-accuracy">
          <div class="flex flex-col gap-0.5">
            <p class="text-base font-medium text-ink-primary">{{ __('Has this been right?') }}</p>
            <p class="text-xs text-ink-muted">{{ scoreNote }}</p>
          </div>
          <template v-if="score.scored">
            <div class="flex flex-col gap-0.5 ps-4">
              <p class="text-xs text-ink-muted">{{ __('Inside the range') }}</p>
              <p class="text-xl font-medium tabular-nums text-ink-primary">
                {{ score.inside_pct }}%
              </p>
            </div>
            <div class="flex flex-col gap-0.5 ps-4">
              <p class="text-xs text-ink-muted">{{ __('Typical miss') }}</p>
              <p class="text-xl font-medium tabular-nums text-ink-primary">
                {{ minutes(score.typical_error_s) }}
              </p>
            </div>
            <div class="flex flex-col gap-0.5 ps-4">
              <p class="text-xs text-ink-muted">{{ __('Hours scored') }}</p>
              <p class="text-xl font-medium tabular-nums text-ink-primary">{{ score.scored }}</p>
            </div>
            <!--
              Plotted as what *missed* rather than what held, and that is the
              chart working rather than a presentational preference. The share
              inside is ninety-nine point something every day, so a plot of it
              is a flat line at the top of an axis that starts at twenty, and
              the day it fell four points is invisible — which is the one day
              the chart exists to show. The complement starts at nought, so a
              bad day is a spike.
            -->
            <div class="h-24 min-w-64 flex-1">
              <LineChart
                :data="missed"
                x="label"
                y="value"
                :title="__('Missed the range')"
                :palette="[delayInk(300)]"
              />
            </div>
          </template>
        </Panel>

        <!--
          Only when a stop has been chosen, because that is the only time there
          is one to answer about. The facet bar is already the way a screen here
          is narrowed to a stop, so this needs no picker of its own — and a
          panel that appeared with an empty control in it would be a question
          asked of a reader who had not asked one.
        -->
        <Panel ground="raised" v-if="facets.stop" class="flex flex-col gap-3" data-slot="outlook-stop">
          <div class="flex items-baseline justify-between gap-2">
            <p class="text-base font-medium text-ink-primary">{{ __('At this stop') }}</p>
            <span class="text-xs text-ink-muted">
              {{ __('{0} on a {1}', [hourLabel, weekdayName]) }}
            </span>
          </div>
          <p v-if="stopAnswer.scheduled_only" class="text-sm text-ink-muted">
            {{ __('No history at this stop in this hour yet. An arrival here is the timetable plus the delay so far.') }}
          </p>
          <div v-else class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div v-for="one in stopFigures" :key="one.title" class="flex flex-col gap-0.5">
              <p class="text-xs text-ink-muted">{{ one.title }}</p>
              <p class="text-xl font-medium tabular-nums text-ink-primary">{{ one.value }}</p>
              <p class="text-xs text-ink-muted">{{ one.note }}</p>
            </div>
          </div>
        </Panel>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { Badge, BarChart, LineChart, NumberCard, Select } from '@/ui'
import Narrow from '@/shared/components/Narrow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { useFacets } from '@/modules/onemobility/lib/facets'
import {
  delayInk,
  divergingRamp,
  occupancyInk,
  troubleInk,
} from '@/modules/onemobility/lib/palette'
import Panel from '@/shared/components/Panel.vue'
import Row from '@/shared/components/Row.vue'

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

// Shared with the map and the charts, and in the URL — `lib/facets.js`.
const { facets, offered, asJson } = useFacets()
const day = ref(today())
const hour = ref('8')

const loading = ref(true)
const ready = ref(false)
const answer = ref({})

const loadingRisk = ref(false)
const riskAnswer = ref({})

const loadingBunching = ref(false)
const bunchingAnswer = ref({})

const unusualReady = ref(false)
const unusualAnswer = ref({})

const loadingFaults = ref(false)
const faultAnswer = ref({})

const stopAnswer = ref({})
const scoreAnswer = ref({})

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
    full_chance: one.full_chance ?? 0,
  }))
)

/**
 * Worst first, and labelled by stop and line together: "Alexanderplatz" is
 * where it happens and "U6" is whose problem it is, and a scheduler needs
 * both to act on it.
 */
const bunches = computed(() =>
  (bunchingAnswer.value.stops || [])
    .slice(0, 10)
    .map((one) => ({ label: `${one.stop} · ${one.line}`, chance: one.chance }))
)

const bunchingSubtitle = computed(() => {
  const share = Math.round((bunchingAnswer.value.share ?? 0.4) * 100)
  const said = __('Percent of gaps under {0}% of the usual one, at {1}:00', [
    share,
    String(hour.value).padStart(2, '0'),
  ])
  // Said on the chart rather than left to the reader. A stop-and-hour figure
  // rests on far fewer observations than a line-and-hour one — a fortnight of
  // Tuesdays at eight is a handful of visits — and a bar drawn from six
  // readings looks exactly like a bar drawn from six hundred.
  const rows = bunchingAnswer.value.stops || []
  return rows.length && rows.every((one) => one.learning)
    ? `${said} · ${__('still learning')}`
    : said
})

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

const faultHours = computed(() => faultAnswer.value.hours || [])

const faultSubtitle = computed(() =>
  __('Share of {0}s with something wrong at this hour', [weekdayName.value])
)

/**
 * How many of that weekday this rests on, and whether that is enough to be a
 * frequency at all. Said in the panel rather than only flagged, because the
 * difference between "on four Tuesdays in thirteen" and "on one Tuesday in
 * one" is the whole reliability of the chart beside it.
 */
const faultBasis = computed(() => {
  const days = faultAnswer.value.days || 0
  if (!days) return ''
  if (faultAnswer.value.learning) {
    return __('Only {0} of them so far, so this is still learning', [days])
  }
  const { from, to } = faultAnswer.value
  return __('Across {0} of them, {1} to {2}', [days, from, to])
})

/** The three figures a shift is planned off. */
const faultFigures = computed(() => {
  const hours = faultHours.value
  if (!hours.length) return []
  const trouble = hours.reduce((sum, one) => sum + (one.trouble || 0), 0)
  const events = hours.reduce((sum, one) => sum + (one.events || 0), 0)
  let worst = null
  for (const one of hours) if (!worst || one.chance > worst.chance) worst = one
  return [
    {
      title: __('Faults in a day'),
      value: Math.round(trouble * 10) / 10,
      note: __('States somebody has to act on'),
    },
    {
      title: __('The hour to staff'),
      value: worst?.label || '—',
      note: __('{0}% of them go wrong then', [worst ? Math.round(worst.chance) : 0]),
    },
    {
      title: __('Reports in a day'),
      value: Math.round(events),
      note: __('Every state change, all kinds'),
    },
  ]
})

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

const score = computed(() => ({
  scored: scoreAnswer.value.scored || 0,
  inside_pct: scoreAnswer.value.inside_pct,
  typical_error_s: scoreAnswer.value.typical_error_s,
  by_day: scoreAnswer.value.by_day || [],
}))

const missed = computed(() =>
  score.value.by_day.map((one) => ({
    label: one.label,
    value: Math.round((100 - one.value) * 10) / 10,
  }))
)

/**
 * The cold start, said plainly. A workspace switched on this week has claims
 * and no answers yet, and "0%" would read as a forecast that is always wrong
 * rather than one that has not been marked.
 */
const scoreNote = computed(() =>
  score.value.scored
    ? __('Every claim was written down the night before, then checked against what happened.')
    : __('Nothing has been scored yet. Each night this writes down what it expects tomorrow, and checks it the night after.')
)

/** What every endpoint here is narrowed by. One object, one place. */
const narrowed = computed(() => ({
  facets: asJson(),
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

async function pullBunching() {
  loadingBunching.value = true
  try {
    bunchingAnswer.value = await network.bunchingRisk(narrowed.value)
  } finally {
    loadingBunching.value = false
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

async function pullFaults() {
  loadingFaults.value = true
  try {
    faultAnswer.value = await network.faults({
      facets: narrowed.value.facets, when: day.value,
    })
  } catch {
    // The event tier is optional — a workspace with no bridge on any vehicle
    // has no table to read — and a screen about the service should not fail
    // because the half about the equipment has nothing in it.
    faultAnswer.value = {}
  } finally {
    loadingFaults.value = false
  }
}

async function pullScore() {
  scoreAnswer.value = await network.accuracy({ facets: narrowed.value.facets })
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
 * The day moves every read but one: `unusual` is about today by definition — a
 * day that has not happened cannot be behaving oddly — so it is fetched once
 * and left alone while somebody scrubs through next week.
 */
watch([facets, day], () => {
  pull()
  pullRisk()
  pullBunching()
  pullStop()
  pullScore()
  pullFaults()
})
watch(hour, () => {
  pullRisk()
  pullBunching()
  pullStop()
})

onMounted(async () => {
  pull()
  pullRisk()
  pullBunching()
  pullUnusual()
  pullScore()
  pullFaults()
})
</script>

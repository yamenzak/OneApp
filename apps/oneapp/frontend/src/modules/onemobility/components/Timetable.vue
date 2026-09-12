<template>
  <!--
    What was published against what ran.

    README §6's other half, and the sentence it opens on: *the planned timetable
    says 07:38 and the vehicle says 07:44*. `conflicts.py` decides which record
    two sources are describing; this compares two statements about the same
    event — and **nothing here resolves it**. The gap is the product. A screen
    that reconciled the two would be throwing away the only number on it worth
    reading.

    Which is why the table is the point and the cards are the summary, rather
    than the other way round. "Ninety-four percent of calls were made" is a
    figure for a board paper; "the 07:38 from Alexanderplatz has been eight
    minutes late every weekday this month" is a thing somebody can go and fix.
  -->
  <div class="h-full min-h-body w-full overflow-y-auto" data-slot="plan">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <div class="flex flex-wrap items-center gap-2" data-slot="plan-controls">
        <FacetBar v-model="facets" :facets="offered" :unavailable="unavailable" />
        <Select v-model="day" :options="dayOptions" class="w-44" />
        <span v-if="kept" class="ms-auto text-sm text-ink-muted">
          {{ __('{0} calls in the timetable', [String(kept)]) }}
        </span>
      </div>

      <EmptyState
        v-if="ready && !answer.planned"
        icon="lucide-calendar"
        :title="__('No timetable for this day')"
        :description="__('A source has to deliver a plan first — GTFS in stop_times, VDV 452 in its travel times.')"
      />

      <template v-else>
        <div
          class="grid auto-rows-tile grid-cols-2 gap-3 lg:grid-cols-4"
          data-slot="plan-headline"
        >
          <NumberCard
            v-for="one in headline"
            :key="one.title"
            :title="one.title"
            :value="one.value ?? 0"
            :suffix="one.suffix"
            :subtitle="one.subtitle"
            :loading="loading"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-80">
            <!--
              How far off the middle call was, hour by hour. One figure for the
              day cannot show the morning peak holding and the afternoon
              falling apart, which is the finding somebody opens this for.
            -->
            <BarChart
              :data="byHour"
              x="label"
              y="minutes"
              :title="__('How late the middle call was')"
              :subtitle="__('Minutes past the published time, hour by hour')"
              :palette="[delayInk(300)]"
              :loading="loading"
            />
          </div>

          <div class="h-80">
            <!--
              And what did not happen at all. An hour with planned calls and no
              median is a suspended service, which is the strongest signal this
              screen carries and is invisible in an average.
            -->
            <BarChart
              :data="byHour"
              x="label"
              y="missed"
              :title="__('Calls nothing came to')"
              :subtitle="__('Planned, and no vehicle within three quarters of an hour')"
              :palette="[occupancyInk(95)]"
              :loading="loading"
            />
          </div>
        </div>

        <!--
          Two lists and not one, because a call that never happened and a call
          that was eight minutes late are different findings and the first
          drowns the second. Sorted together, forty rows of "nothing came" is
          all anybody ever sees — and the late list is the one that gets a
          timetable changed.
        -->
        <div class="grid grid-cols-1 gap-3 xl:grid-cols-2" data-slot="plan-calls">
          <Panel ground="raised" class="flex flex-col gap-2">
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-base font-medium text-ink-primary">{{ __('Nothing came') }}</p>
              <span class="text-xs text-ink-muted">{{ __('Published, and not run') }}</span>
            </div>
            <CallList :calls="missed" />
          </Panel>

          <Panel ground="raised" class="flex flex-col gap-2">
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-base font-medium text-ink-primary">{{ __('Furthest from the plan') }}</p>
              <span class="text-xs text-ink-muted">{{ __('Worst first') }}</span>
            </div>
            <CallList :calls="late" />
          </Panel>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { BarChart, NumberCard, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'
import { delayInk, occupancyInk } from '@/modules/onemobility/lib/palette'
import CallList from '@/modules/onemobility/components/CallList.vue'
import FacetBar from '@/modules/onemobility/components/FacetBar.vue'
import Panel from '@/shared/components/Panel.vue'

defineProps({
  /** The resolved screen. Unused: this surface reads no records. */
  spec: { type: Object, default: () => ({}) },
})

/** How many days back the picker offers. The plan is a weekly pattern, so a
 *  fortnight is every weekday twice — enough to tell a bad Tuesday from a bad
 *  line. */
const BACK = 14

const facets = ref({})
const offered = ref([])
const day = ref(yesterday())
const loading = ref(true)
const ready = ref(false)
const answer = ref({})

/** Yesterday, not today: a day still running has calls that have not come yet,
 *  and counting those as missed would report every morning as a disaster. */
function yesterday() {
  const at = new Date()
  at.setDate(at.getDate() - 1)
  return at.toISOString().slice(0, 10)
}

const dayOptions = computed(() => {
  const options = []
  for (let step = 1; step <= BACK; step += 1) {
    const at = new Date()
    at.setDate(at.getDate() - step)
    const iso = at.toISOString().slice(0, 10)
    options.push({ label: iso, value: iso })
  }
  return options
})

const unavailable = computed(() => answer.value.unavailable || [])
const kept = computed(() => answer.value.kept || 0)
const calls = computed(() => answer.value.calls || [])
const missed = computed(() => calls.value.filter((one) => one.gap_s === null).slice(0, 20))
const late = computed(() => calls.value.filter((one) => one.gap_s !== null).slice(0, 20))

const byHour = computed(() =>
  (answer.value.by_hour || []).map((one) => ({
    label: one.label,
    // Minutes, because this is a chart a person reads rather than a series a
    // machine consumes, and nobody says "four hundred and eighty seconds".
    minutes: one.median_s === null ? 0 : Math.round((one.median_s / 60) * 10) / 10,
    missed: one.missed,
  }))
)

const headline = computed(() => {
  const out = answer.value
  const made = out.planned ? Math.round((100 * out.matched) / out.planned) : null
  return [
    {
      title: __('Calls planned'),
      value: out.planned ?? 0,
      subtitle: __('What the timetable said would happen'),
    },
    {
      title: __('Made'),
      value: made ?? 0,
      suffix: '%',
      subtitle: __('{0} of {1}', [String(out.matched ?? 0), String(out.planned ?? 0)]),
    },
    {
      title: __('Nothing came'),
      value: out.missed ?? 0,
      subtitle: __('Planned, and no vehicle inside the window'),
    },
    {
      title: __('Typical gap'),
      value: out.median_s === null || out.median_s === undefined
        ? 0
        : Math.round((out.median_s / 60) * 10) / 10,
      suffix: __('min'),
      subtitle: __('The middle call, against its published time'),
    },
  ]
})

async function pull() {
  loading.value = true
  try {
    answer.value = await network.deviation({
      day: day.value,
      facets: JSON.stringify(facets.value),
    })
  } finally {
    loading.value = false
    ready.value = true
  }
}

watch([facets, day], pull)

onMounted(async () => {
  offered.value = (await network.offered()).facets || []
  pull()
})
</script>

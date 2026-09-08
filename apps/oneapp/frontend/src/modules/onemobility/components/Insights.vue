<template>
  <!--
    The aggregate tier, looked at.

    Four figures and four plots, all off `serviceHour` — the tier the nightly
    roll-up writes and nothing deletes. Nothing here is predicted: what a
    Tuesday at eight looks like *is* every Tuesday at eight that has happened,
    which is both more useful to a scheduler and more defensible to a regulator
    than a number a model produced. See `onemobility/README.md` §7a.

    A `component` screen and not a dashboard view, for one reason: a dashboard
    widget counts a doctype's rows, and none of this is a doctype. The
    aggregate tier is outside the document system by design.
  -->
  <div class="h-full min-h-[28rem] w-full overflow-y-auto" data-slot="insights">
    <div class="mx-auto flex max-w-7xl flex-col gap-4 p-1">
      <!-- What is being read, and over how long. -->
      <div class="flex flex-wrap items-center gap-2" data-slot="insights-controls">
        <Select
          v-model="line"
          :options="lineOptions"
          :placeholder="__('Every line')"
          class="w-52"
          @change="pull"
        />
        <Select
          v-model="range"
          :options="rangeOptions"
          class="w-40"
          @change="pull"
        />
        <span class="ms-auto text-sm text-ink-gray-5">{{ window }}</span>
      </div>

      <EmptyState
        v-if="ready && !headline.length"
        icon="lucide-chart-column"
        :title="__('Nothing measured yet')"
        :description="__('Connect a source and let a day go by, and this fills in.')"
      />

      <template v-else>
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <NumberCard
            v-for="one in headline"
            :key="one.label"
            :title="one.label"
            :value="one.value ?? 0"
            :suffix="one.suffix"
            :loading="loading"
            compact
          />
        </div>

        <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div class="h-72">
            <AreaChart
              :data="byHour"
              x="label"
              y="value"
              :title="__('Lateness through the day')"
              :subtitle="__('Seconds behind the timetable, weighted by how much was seen')"
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

        <div class="h-80">
          <BarChart
            :data="byLine"
            x="label"
            y="value"
            horizontal
            :title="__('Which lines run late')"
            :subtitle="__('Average minutes behind the timetable, every line')"
            :loading="loading"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { AreaChart, BarChart, HeatmapChart, NumberCard, Select } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { network } from '@/modules/onemobility/lib/api'

defineProps({
  /** The resolved screen. Unused: this surface reads no records. */
  spec: { type: Object, default: () => ({}) },
})

const line = ref('')
const range = ref('30')
const ready = ref(false)
const loading = ref(true)
const answer = ref({})

const headline = computed(() => answer.value.headline || [])
const byHour = computed(() => answer.value.by_hour || [])
const loadByHour = computed(() => answer.value.load_by_hour || [])
const week = computed(() => answer.value.week || [])
const byLine = computed(() => answer.value.by_line || [])

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

onMounted(pull)
</script>

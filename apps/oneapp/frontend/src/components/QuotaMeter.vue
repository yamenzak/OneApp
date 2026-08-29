<template>
  <div v-if="quota" class="hidden items-center gap-2 sm:flex" :title="title">
    <div class="h-1.5 w-24 overflow-hidden rounded-full bg-gray-200">
      <div class="h-full rounded-full transition-all" :class="barClass" :style="barStyle" />
    </div>
    <span class="text-xs tabular-nums text-gray-600">{{ percent }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { session, storageFraction, formatBytes } from '../lib/session'

const quota = computed(() =>
  session.quota?.storage_quota_bytes ? session.quota : null,
)

const fraction = computed(() => Math.min(storageFraction(), 1))
const percent = computed(() => Math.round(fraction.value * 100))
const barStyle = computed(() => ({ width: `${Math.max(fraction.value * 100, 2)}%` }))

// Warn well before the hard block, so running out is never a surprise.
const barClass = computed(() => {
  if (fraction.value >= 1) return 'bg-red-600'
  if (fraction.value >= 0.8) return 'bg-amber-500'
  return 'bg-gray-900'
})

const title = computed(
  () =>
    `${formatBytes(session.quota.storage_used_bytes)} of ` +
    `${formatBytes(session.quota.storage_quota_bytes)} used`,
)
</script>

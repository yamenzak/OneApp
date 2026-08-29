<template>
  <Tooltip v-if="quota" :text="label">
    <div class="flex min-w-0 items-center gap-2">
      <Progress :value="percent" size="sm" class="w-20" />
      <span class="shrink-0 text-p-sm tabular-nums text-ink-gray-5">{{ percent }}%</span>
    </div>
  </Tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Progress, Tooltip } from '@/ui'
import { session, storageFraction, formatBytes } from '../lib/session'

const quota = computed(() => (session.quota?.storage_quota_bytes ? session.quota : null))
const percent = computed(() => Math.round(Math.min(storageFraction.value, 1) * 100))
const label = computed(
  () =>
    `${formatBytes(session.quota.storage_used_bytes)} of ` +
    `${formatBytes(session.quota.storage_quota_bytes)} used`,
)
</script>

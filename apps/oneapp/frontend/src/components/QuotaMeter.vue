<template>
  <Tooltip v-if="storage?.quota" :text="label">
    <div class="flex min-w-0 items-center gap-2">
      <Progress :value="percent" :theme="theme" size="sm" class="w-20" />
      <span class="shrink-0 text-p-sm tabular-nums text-ink-gray-5">{{ percent }}%</span>
    </div>
  </Tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Progress, Tooltip } from '@/ui'
import { session } from '../lib/session'

// The server sends labels alongside the numbers so byte formatting is done in
// one place rather than reimplemented per component.
const storage = computed(() => session.quota?.storage || null)
const percent = computed(() => Math.round(Math.min(storage.value?.fraction || 0, 1) * 100))

const theme = computed(() => {
  if (storage.value?.exceeded) return 'red'
  if (storage.value?.warn) return 'orange'
  return 'blue'
})

const label = computed(
  () => `${storage.value.used_label} of ${storage.value.quota_label} used`,
)
</script>

<template>
  <Tooltip v-if="storage?.quota" :text="label">
    <div class="flex min-w-0 items-center gap-2">
      <Progress :value="percent" size="sm" :class="['w-20', barClass]" />
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

// Progress has no `theme`: its fill is always `bg-surface-gray-10`, so the
// colour has to be applied from outside. `class` falls through to the root, and
// the fill is the element inside `role="progressbar"` — `!` because the
// component's own background class is on that same element.
const barClass = computed(() => {
  if (storage.value?.exceeded) return '[&_[role=progressbar]>*]:!bg-surface-red-6'
  if (storage.value?.warn) return '[&_[role=progressbar]>*]:!bg-surface-amber-5'
  return ''
})

const label = computed(
  () => `${storage.value.used_label} of ${storage.value.quota_label} used`,
)
</script>

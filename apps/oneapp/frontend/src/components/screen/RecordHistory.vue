<template>
  <div class="flex flex-col gap-3 pt-4">
    <LoadingText v-if="loading" text="Loading history" />

    <EmptyState
      v-else-if="!changes.length"
      class="!py-8"
      icon="lucide-history"
      title="No changes recorded"
      description="Nothing on this screen has changed since it was created."
    />

    <!--
      In the screen's own words. Frappe stores a version as raw field names,
      and "grand_total: 120 → 140" for a field the customer's screen calls
      "Total" reads as though it belongs to something else.
    -->
    <div v-for="entry in changes" :key="entry.name" class="flex gap-3">
      <Avatar :label="entry.by" size="sm" />
      <div class="min-w-0 flex-1">
        <div class="flex items-baseline gap-2">
          <span class="truncate text-p-sm font-medium text-ink-gray-8">{{ entry.by }}</span>
          <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(entry.on) }}</span>
        </div>
        <p v-for="(change, i) in entry.entries" :key="i" class="text-p-sm text-ink-gray-6">
          <span class="text-ink-gray-8">{{ change.label }}</span>
          <span class="text-ink-gray-4"> {{ change.from || '—' }} → </span>
          <span class="text-ink-gray-8">{{ change.to || '—' }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Avatar, LoadingText, dayjsLocal } from '@/ui'
import EmptyState from '../EmptyState.vue'

defineProps({
  changes: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')
</script>

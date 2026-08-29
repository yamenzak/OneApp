<template>
  <div class="mx-auto max-w-2xl p-8">
    <h1 class="text-xl font-semibold">Account</h1>

    <dl class="mt-6 divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
      <div v-for="row in rows" :key="row.label" class="flex justify-between px-4 py-3">
        <dt class="text-sm text-gray-600">{{ row.label }}</dt>
        <dd class="text-sm font-medium tabular-nums">{{ row.value }}</dd>
      </div>
    </dl>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { session, formatBytes } from '../lib/session'

const rows = computed(() => [
  { label: 'Workspace', value: session.tenant?.name || '—' },
  { label: 'Plan', value: session.tenant?.plan || '—' },
  { label: 'Signed in as', value: session.user?.name || '—' },
  {
    label: 'Storage',
    value: `${formatBytes(session.quota?.storage_used_bytes)} of ${formatBytes(
      session.quota?.storage_quota_bytes,
    )}`,
  },
  { label: 'Credits', value: Math.round(session.credits?.balance ?? 0) },
])
</script>

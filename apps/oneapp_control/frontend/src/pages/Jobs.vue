<template>
  <div class="mx-auto max-w-5xl p-8">
    <PageHeader>
      <template #title><h1 class="text-xl font-semibold">Provisioning</h1></template>
      <template #actions>
        <Button :loading="loading" label="Refresh" @click="load" />
      </template>
    </PageHeader>

    <p class="mt-1 text-p-base text-ink-gray-6">
      Updates arrive live. Jobs advance on a two-minute cron, so a new one sits at
      Requested briefly; each step is idempotent and a failure retries with backoff.
    </p>

    <div v-if="loading && !jobs.length" class="mt-8 grid place-items-center">
      <LoadingIndicator class="h-5 w-5 text-ink-gray-5" />
    </div>

    <div v-else class="mt-6 divide-y divide-outline-gray-1 rounded border border-outline-gray-2">
      <div v-for="job in jobs" :key="job.name" class="p-3">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-p-base font-medium">
              {{ job.action }} — {{ job.tenant }}
            </p>
            <p class="truncate text-p-sm text-ink-gray-5">
              {{ job.step || 'not started' }}
              <span v-if="job.attempts > 1"> · attempt {{ job.attempts }}</span>
            </p>
          </div>
          <Badge :theme="theme(job.state)" :label="job.state" />
        </div>
        <p v-if="job.last_error" class="mt-2 rounded bg-surface-red-1 p-2 text-p-sm text-ink-red-3">
          {{ job.last_error }}
        </p>
      </div>
      <p v-if="!jobs.length" class="p-6 text-center text-p-sm text-ink-gray-5">
        No provisioning jobs yet.
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Button, Badge, LoadingIndicator } from '@/ui'
import { useList } from '../lib/api'

// Provisioning Job changes arrive over the socket, so this tracks a running job
// step by step with no polling.
const resource = useList('Provisioning Job', {
  fields: ['name', 'tenant', 'action', 'state', 'step', 'attempts', 'last_error'],
  orderBy: 'creation desc',
  limit: 25,
})
const jobs = computed(() => resource.data || [])
const loading = computed(() => resource.loading)

const theme = (state) =>
  ({
    Succeeded: 'green',
    Failed: 'red',
    Running: 'blue',
    'Awaiting Agent': 'blue',
    Requested: 'gray',
    Cancelled: 'gray',
  })[state] || 'gray'

const load = () => resource.reload()
</script>

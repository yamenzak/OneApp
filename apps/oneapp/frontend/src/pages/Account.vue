<template>
  <PageHeader>
    <span class="text-base-medium text-ink-gray-8">Account</span>
</PageHeader>

  <div class="mx-auto max-w-2xl p-5">
    <div v-if="!session.loaded" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <template v-else>
      <div class="rounded-6 border border-outline-gray-2 bg-surface-base">
        <div
          v-for="row in rows"
          :key="row.label"
          class="flex items-center justify-between gap-4 border-b border-outline-gray-1 px-4 py-3 last:border-b-0"
        >
          <span class="text-p-base text-ink-gray-6">{{ row.label }}</span>
          <span class="text-p-base font-medium tabular-nums text-ink-gray-8">
            {{ row.value }}
          </span>
        </div>
      </div>

      <h2 class="mt-8 text-base-medium text-ink-gray-8">Usage</h2>
      <div class="mt-3 flex flex-col gap-5 rounded-6 border border-outline-gray-2 bg-surface-base p-4">
        <UsageBar
          label="Files"
          :usage="quota.storage"
          exceeded-hint="Uploads are paused. Delete some files, or buy more storage."
        />
        <UsageBar
          label="Database"
          :usage="quota.database"
          exceeded-hint="New records are paused. Your data is intact — delete something, or upgrade."
        />
        <UsageBar label="Background jobs" :usage="jobUsage" format="count" />
      </div>

      <h2 class="mt-8 text-base-medium text-ink-gray-8">Preferences</h2>
      <div class="mt-3 rounded-6 border border-outline-gray-2 bg-surface-base p-4">
        <ThemeSetting />
      </div>

      <p class="mt-4 text-p-sm text-ink-gray-5">
        Billing, storage add-ons and your plan are managed in your {{ TENANT_APP }} account.
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, LoadingIndicator } from '@/ui'
import UsageBar from '../components/UsageBar.vue'
import ThemeSetting from '../components/ThemeSetting.vue'
import { TENANT_APP } from '../lib/brand'
import { session } from '../lib/session'

const quota = computed(() => session.quota || {})

const rows = computed(() => [
  { label: 'Workspace', value: session.tenant?.name || '—' },
  { label: 'Plan', value: session.tenant?.plan || '—' },
  { label: 'Signed in as', value: session.user?.name || '—' },
  { label: 'Credits', value: Math.round(session.credits?.balance ?? 0) },
])

// Shaped like the other meters so one component renders all three. Jobs have no
// warning band — being at the limit is momentary and expected, not a problem to
// flag ahead of time.
const jobUsage = computed(() => {
  const jobs = quota.value.jobs
  if (!jobs?.limit) return null
  return {
    used: jobs.running,
    quota: jobs.limit,
    fraction: jobs.running / jobs.limit,
    warn: false,
    exceeded: jobs.at_limit,
  }
})
</script>

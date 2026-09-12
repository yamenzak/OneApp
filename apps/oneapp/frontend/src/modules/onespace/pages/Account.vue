<template>
  <PageHeader>
    <Trail :items="crumbs" />
  </PageHeader>

  <div class="mx-auto max-w-2xl p-5">
    <div v-if="!session.loaded" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-muted" />
    </div>

    <template v-else>
      <Panel pad="none">
        <div
          v-for="row in rows"
          :key="row.label"
          class="flex items-center justify-between gap-4 border-b border-outline-gray-1 px-4 py-3 last:border-b-0"
        >
          <span class="text-p-base text-ink-secondary">{{ row.label }}</span>
          <span class="text-p-base font-medium tabular-nums text-ink-primary">
            {{ row.value }}
          </span>
        </div>
      </Panel>

      <h2 class="mt-8 text-base-medium text-ink-primary">{{ __('Usage') }}</h2>
      <Panel class="mt-3 flex flex-col gap-5">
        <UsageBar
          :label="__('Files')"
          :usage="quota.storage"
          :exceeded-hint="__('Uploads are paused. Delete some files, or buy more storage.')"
        />
        <UsageBar
          :label="__('Records')"
          :usage="quota.database"
          :exceeded-hint="__('New records are paused. Nothing is lost — delete something, or upgrade.')"
        />
        <UsageBar :label="__('Background jobs')" :usage="jobUsage" format="count" />
      </Panel>

      <h2 class="mt-8 text-base-medium text-ink-primary">{{ __('Preferences') }}</h2>
      <Panel class="mt-3 flex flex-col gap-5">
        <ThemeSetting />
        <NotificationSettings />
      </Panel>

      <p class="mt-4 text-p-sm text-ink-muted">
        {{ __('Billing, storage add-ons and your plan are in your {0} account.', [TENANT_APP]) }}
      </p>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, LoadingIndicator } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import ThemeSetting from '@/modules/onespace/components/ThemeSetting.vue'
import NotificationSettings from '@/modules/onespace/components/notifications/NotificationSettings.vue'
import { TENANT_APP } from '@/shared/lib/runtime/brand'
import { __ } from '@/shared/lib/runtime/translate'
import { session } from '@/modules/onespace/lib/shell/session'
import Panel from '@/shared/components/Panel.vue'

const quota = computed(() => session.quota || {})

const rows = computed(() => [
  { label: __('Workspace'), value: session.tenant?.name || '—' },
  { label: __('Plan'), value: session.tenant?.plan || '—' },
  { label: __('Signed in as'), value: session.user?.name || '—' },
  { label: __('Credits'), value: Math.round(session.credits?.balance ?? 0) },
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

// One root for every surface — §C1.
const crumbs = useCrumbs({ label: __('Account'), route: { name: 'Account' } })
</script>

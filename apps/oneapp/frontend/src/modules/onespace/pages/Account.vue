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

      <!--
        Configuration is not here — §E7. Account is the commercial
        relationship: the plan, the credits, the quota you are against.
        Everything you *set* is in Settings, and these two panels used to be
        rendered here as well as there, which is one component in two chromes
        and two places a person has to remember to look. Now they are links,
        which is what `?panel=` made possible.
      -->
      <h2 class="mt-8 text-base-medium text-ink-primary">{{ __('Yours to set') }}</h2>
      <Panel pad="none" class="mt-3">
        <button
          v-for="one in preferences"
          :key="one.panel"
          type="button"
          data-slot="account-to-settings"
          :class="[HOVER, 'flex w-full items-center gap-3 border-b border-outline-gray-1 px-4 py-3 text-start last:border-b-0']"
          @click="openSettings(one.panel)"
        >
          <Icon :name="one.icon" class="size-4 shrink-0 text-ink-muted" />
          <span class="min-w-0 flex-1 text-p-base text-ink-secondary">{{ one.label }}</span>
          <Icon name="lucide-chevron-right" class="size-4 shrink-0 text-ink-muted" />
        </button>
      </Panel>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon, PageHeader, LoadingIndicator } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import { HOVER } from '@/shared/lib/rowstate'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
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

//: The two Settings tabs that are about this person rather than about the
//: workspace, so an Account page that is somebody's own has a way to them.
//: Named here rather than derived: `tabs.py` returns what a reader may open,
//: and these two are always openable — every audience includes `everyone`.
const preferences = [
  { panel: 'appearance', icon: 'lucide-sun-moon', label: __('How this looks') },
  { panel: 'notifications', icon: 'lucide-bell-dot', label: __('What you are told about') },
]

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

<!--
  Ported from the portal SPA. The content and its reasoning are unchanged; what
  moved is the frame: a screen renders inside the shell's own header, so the
  PageHeader is gone and the workspace it is about is stated by WorkspaceBar
  rather than carried in the route.
-->
<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-measure px-3 pb-10 sm:px-5">
  <div v-if="data" class="flex flex-col gap-6 py-5">
    <!--
      The ladder, said out loud. Every step of it is also an email, and an email
      is the one thing somebody can miss — so the dates appear here too, on the
      page they open when they wonder what is going on.

      Ordered by how bad it is. Only the worst one shows: three stacked alerts
      about the same unpaid subscription is noise, and the one that matters is
      always the one furthest down the ladder.
    -->
    <Alert
      v-if="lifecycle.deleted_on"
      theme="red"
      :title="__('This workspace is scheduled for deletion')"
    >
      <template #description>
        {{ __('On {0} everything held for this workspace is deleted for good — the database, every file and every backup. Paying before then restores it in full.', [date(lifecycle.deleted_on)]) }}
      </template>
    </Alert>

    <Alert
      v-else-if="lifecycle.archives_on"
      theme="red"
      :title="__('This workspace is switched off')"
    >
      <template #description>
        {{ __('Your work has not been touched, and paying brings it back within a minute. If it is still unpaid on {0}, the workspace comes down and only a backup is kept.', [date(lifecycle.archives_on)]) }}
      </template>
    </Alert>

    <Alert
      v-else-if="lifecycle.suspends_on"
      theme="amber"
      :title="__('Your last payment did not go through')"
    >
      <template #description>
        {{ __('Nothing has changed yet and your workspace works normally. Pay by {0} or it is switched off until you do.', [date(lifecycle.suspends_on)]) }}
      </template>
    </Alert>

    <!--
      Over quota is its own thing and can happen to a workspace that is paid up
      — usually because an add-on stopped being billed, which is a sentence the
      person reading this did not cause and cannot guess.
    -->
    <Alert
      v-if="grace"
      theme="amber"
      :title="__('Over the limit for {0}', [limitNames(overQuota)])"
    >
      <template #description>
        {{ __('Nothing is blocked and nothing has been deleted. Until {0} the workspace works normally, except that it cannot grow past where it is now. After that, new uploads stop until there is room.', [date(grace)]) }}
      </template>
    </Alert>

    <Alert
      v-else-if="exceeded.length"
      theme="amber"
      :title="__('At the limit for {0}', [limitNames(exceeded)])"
    >
      <template #description>
        {{ __('Nothing has been deleted. Free some space, or add more below — new uploads resume as soon as there is room.') }}
      </template>
    </Alert>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-primary">{{ __('Usage') }}</h3>
      <div class="flex flex-col gap-4 rounded-6 border border-outline-gray-2 p-4">
        <!--
          The window applies to whichever resource is over, so it is passed to
          both. A bar that is not over ignores it.
        -->
        <UsageBar :label="__('Files')" :usage="data.usage.storage" :grace-until="graceLabel" />
        <UsageBar :label="__('Database')" :usage="data.usage.database" :grace-until="graceLabel" />
        <UsageBar
          :label="__('People')"
          :usage="data.usage.users"
          format="count"
          :exceeded-hint="__('Every seat is taken. Change plan to invite more people.')"
        />
      </div>
    </section>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-primary">{{ __('AI credits') }}</h3>
      <div class="rounded-6 border border-outline-gray-2 p-4">
        <div class="flex items-baseline justify-between">
          <span class="text-2xl-medium tabular-nums text-ink-gray-9">
            {{ Math.round(data.credits.available) }}
          </span>
          <span class="text-p-sm text-ink-muted">{{ __('available') }}</span>
        </div>
        <p class="mt-1.5 text-p-sm text-ink-secondary">
          {{ __('Your plan adds credits every month and they do not carry over. Credits you buy never expire.') }}
        </p>
      </div>
    </section>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-primary">{{ __('Workspace') }}</h3>
      <List :columns="['10rem', 'minmax(0,1fr)']" divider="full">
        <ListRows :items="details" row-key="label" v-slot="{ item: row, value }">
          <!-- Static rows wrap, so no rowHeight — the family leaves height
               auto without one. frappe-ui pads only interactive rows, so the
               vertical rhythm here is this page's to set. -->
          <ListRow :value="value" class="py-3">
            <ListCell>
              <span class="text-p-sm text-ink-secondary">{{ row.label }}</span>
            </ListCell>
            <ListCell>
              <span class="truncate text-sm text-ink-primary">{{ row.value }}</span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>

  <div v-else class="grid place-items-center py-16">
    <LoadingIndicator class="size-5 text-ink-muted" />
  </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Alert, LoadingIndicator, List, ListRows, ListRow, ListCell, dayjsLocal } from '@/ui'
import WorkspaceBar from '@/modules/onespace/screens/account/WorkspaceBar.vue'
import { useWorkspace } from '@/modules/onespace/screens/account/workspace'
// The generated one, and the only one. `screens/account/` carried its own copy
// from the port, identical to it — so an edit to the component the generator
// owns changed nothing here, and the two rendered differently with no way to
// see why from either file.
import UsageBar from '@/modules/onespace/components/UsageBar.vue'
import { useOverview } from '@/modules/onespace/screens/account/customer'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({ spaceCode: { type: String, default: '' }, screen: { type: String, default: '' } })
const workspace = useWorkspace()
const resource = useOverview(workspace)

const data = computed(() => resource.data)

// The server names a limit the way it stores it — `storage`, `users`. A reader
// owns files and people, so the banner says those, and anything unrecognised
// falls through as it came rather than disappearing.
const LIMIT_NAMES = () => ({
  storage: __('files'),
  database: __('database'),
  users: __('people'),
})
const limitNames = (keys) => keys.map((key) => LIMIT_NAMES()[key] || key).join(', ')

const lifecycle = computed(() => data.value?.lifecycle || {})
const overQuota = computed(() => lifecycle.value.over_quota?.over || [])

// The grace window, when one is open. `enforced` false is the whole test: the
// dates beside it describe a window that has already closed once it is true.
const grace = computed(() => {
  const block = lifecycle.value.over_quota
  return block && !block.enforced ? block.grace_until : ''
})

const date = (value) => (value ? dayjsLocal(value).format('D MMMM YYYY') : '')
const graceLabel = computed(() => date(grace.value))

const exceeded = computed(() => {
  const usage = data.value?.usage || {}
  return Object.entries(usage)
    .filter(([, u]) => u.exceeded)
    .map(([name]) => name)
})

const details = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: __('Address'), value: d.workspace.url || '—' },
    { label: __('Custom domain'), value: d.workspace.custom_domain || __('Not set') },
    { label: __('Plan'), value: d.plan.name || '—' },
    { label: __('Region'), value: d.workspace.region || '—' },
    { label: __('Data location'), value: d.workspace.storage_jurisdiction || __('Global') },
    { label: __('Status'), value: d.workspace.status },
    // A plan term people pay for and could otherwise not see — and the fastest
    // way to notice a workspace has quietly stopped backing up.
    { label: __('Backups'), value: backups(d.backups) },
  ]
})

// Built from whole sentences rather than glued fragments: where the date goes
// in "kept 7 days — last 3 May" is not the same question in every language.
const backups = (block) => {
  if (!block?.per_day) return __('Not on this plan')
  const rate =
    block.per_day === 1 ? __('Daily') : __('{0} times a day', [block.per_day])
  const kept = block.retention_days
    ? __('{0}, kept {1} days', [rate, block.retention_days])
    : rate
  return block.last_on
    ? __('{0} — last {1}', [kept, date(block.last_on)])
    : __('{0} — none yet', [kept])
}
</script>

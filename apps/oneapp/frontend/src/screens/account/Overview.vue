<!--
  Ported from the portal SPA. The content and its reasoning are unchanged; what
  moved is the frame: a screen renders inside the shell's own header, so the
  PageHeader is gone and the workspace it is about is stated by WorkspaceBar
  rather than carried in the route.
-->
<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
  <div v-if="data" class="flex flex-col gap-6 py-5">
    <!--
      The ladder, said out loud. Every step of it is also an email, and an email
      is the one thing somebody can miss — so the dates appear here too, on the
      page they open when they wonder what is going on.

      Ordered by how bad it is. Only the worst one shows: three stacked alerts
      about the same unpaid subscription is noise, and the one that matters is
      always the one furthest down the ladder.
    -->
    <Alert v-if="lifecycle.deleted_on" theme="red" title="This workspace is scheduled for deletion">
      <template #description>
        On {{ date(lifecycle.deleted_on) }} everything we hold for this
        workspace is permanently deleted — the database, every file and every
        backup. Paying before then restores it in full.
      </template>
    </Alert>

    <Alert
      v-else-if="lifecycle.archives_on"
      theme="red"
      title="This workspace is switched off"
    >
      <template #description>
        Your data has not been touched and paying brings it back within a
        minute. If it is still unpaid on {{ date(lifecycle.archives_on) }} we
        remove the running site and keep a copy instead.
      </template>
    </Alert>

    <Alert
      v-else-if="lifecycle.suspends_on"
      theme="amber"
      title="We could not take payment"
    >
      <template #description>
        Nothing has changed yet and your workspace is working normally. If the
        payment has not gone through by {{ date(lifecycle.suspends_on) }} it
        will be switched off until it does.
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
      :title="`Over the ${overQuota.join(' and ')} limit`"
    >
      <template #description>
        Nothing is blocked and nothing has been deleted. Until
        {{ date(grace) }} the workspace works normally, except that it cannot
        grow past where it is now. After that, new uploads stop until there is
        room.
      </template>
    </Alert>

    <Alert
      v-else-if="exceeded.length"
      theme="amber"
      :title="`At the ${exceeded.join(' and ')} limit`"
    >
      <template #description>
        Nothing has been deleted. Free some space, or add more below — new uploads
        resume as soon as there is room.
      </template>
    </Alert>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-gray-8">Usage</h3>
      <div class="flex flex-col gap-4 rounded-6 border border-outline-gray-2 p-4">
        <UsageBar label="File storage" :usage="data.usage.storage" />
        <UsageBar label="Database" :usage="data.usage.database" />
        <UsageBar
          label="Members"
          :usage="data.usage.users"
          format="count"
          exceeded-hint="Every seat is taken. Upgrade to invite more people."
        />
      </div>
    </section>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-gray-8">AI credits</h3>
      <div class="rounded-6 border border-outline-gray-2 p-4">
        <div class="flex items-baseline justify-between">
          <span class="text-2xl-medium tabular-nums text-ink-gray-9">
            {{ Math.round(data.credits.available) }}
          </span>
          <span class="text-p-sm text-ink-gray-5">available</span>
        </div>
        <p class="mt-1.5 text-p-sm text-ink-gray-6">
          Your plan grants {{ plan?.name }} credits each period. Unused plan credits
          do not carry over; purchased packs never expire.
        </p>
      </div>
    </section>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-gray-8">Workspace</h3>
      <List :columns="['10rem', 'minmax(0,1fr)']" divider="full">
        <ListRows :items="details" row-key="label" v-slot="{ item: row, value }">
          <!-- Static rows wrap, so no rowHeight — the family leaves height
               auto without one. frappe-ui pads only interactive rows, so the
               vertical rhythm here is this page's to set. -->
          <ListRow :value="value" class="py-3">
            <ListCell>
              <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
            </ListCell>
            <ListCell>
              <span class="truncate text-p-sm text-ink-gray-8">{{ row.value }}</span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>

  <div v-else class="grid place-items-center py-16">
    <LoadingIndicator class="size-5 text-ink-gray-5" />
  </div>
  </div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { Alert, LoadingIndicator, List, ListRows, ListRow, ListCell, dayjsLocal } from '@/ui'
import WorkspaceBar from './WorkspaceBar.vue'
import { useWorkspace } from './workspace'
import UsageBar from './UsageBar.vue'
import { useOverview } from './customer'

defineProps({ spaceCode: { type: String, default: '' }, screen: { type: String, default: '' } })
const workspace = useWorkspace()
const resource = useOverview(workspace)

const data = computed(() => resource.data)
const plan = computed(() => data.value?.plan)

const lifecycle = computed(() => data.value?.lifecycle || {})
const overQuota = computed(() => lifecycle.value.over_quota?.over || [])

// The grace window, when one is open. `enforced` false is the whole test: the
// dates beside it describe a window that has already closed once it is true.
const grace = computed(() => {
  const block = lifecycle.value.over_quota
  return block && !block.enforced ? block.grace_until : ''
})

const date = (value) => (value ? dayjsLocal(value).format('D MMMM YYYY') : '')

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
    { label: 'Address', value: d.workspace.url || '—' },
    { label: 'Custom domain', value: d.workspace.custom_domain || 'Not set' },
    { label: 'Plan', value: d.plan.name || '—' },
    { label: 'Region', value: d.workspace.region || '—' },
    { label: 'Data location', value: d.workspace.storage_jurisdiction || 'Global' },
    { label: 'Status', value: d.workspace.status },
    // A plan term people pay for and could otherwise not see — and the fastest
    // way to notice a workspace has quietly stopped backing up.
    { label: 'Backups', value: backups(d.backups) },
  ]
})

const backups = (block) => {
  if (!block?.per_day) return 'Not on this plan'
  const rate = block.per_day === 1 ? 'Daily' : `${block.per_day} times a day`
  const kept = block.retention_days ? `, kept ${block.retention_days} days` : ''
  const last = block.last_on ? ` — last ${date(block.last_on)}` : ' — none yet'
  return `${rate}${kept}${last}`
}
</script>

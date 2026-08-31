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
    <Alert
      v-if="exceeded.length"
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
import { Alert, LoadingIndicator, List, ListRows, ListRow, ListCell } from '@/ui'
import WorkspaceBar from './WorkspaceBar.vue'
import { useWorkspace } from './workspace'
import UsageBar from './UsageBar.vue'
import { useOverview } from './customer'

defineProps({ spaceCode: { type: String, default: '' }, screen: { type: String, default: '' } })
const workspace = useWorkspace()
const resource = useOverview(workspace)

const data = computed(() => resource.data)
const plan = computed(() => data.value?.plan)

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
  ]
})
</script>

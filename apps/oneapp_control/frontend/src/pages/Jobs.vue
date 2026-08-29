<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: 'Provisioning' }]" />
  
    <div class="flex items-center gap-2">
      <Button :loading="resource.loading" label="Refresh" @click="resource.reload()" />
</div>
  </PageHeader>

  <div class="p-5">
    <p class="mb-4 text-p-base text-ink-gray-6">
      Updates arrive live. Jobs advance on a two-minute cron, so a new one waits at
      Requested briefly; every step is idempotent and a failure retries with backoff.
    </p>

    <EmptyState
      v-if="!rows.length && !resource.loading"
      title="No provisioning jobs"
      description="Jobs appear here when a tenant is created, suspended, resumed or archived."
    />

    <List v-else :columns="columns" :row-height="52" class="list-row-px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="rows" row-key="name" v-slot="{ item: job, value }">
        <ListRow :value="value">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ job.action }}</p>
              <!-- The step is a column of its own where there is room, and part
                   of the subtitle where there is not: which step a job is on is
                   the thing you came to see. -->
              <p class="truncate text-xs text-ink-gray-5">
                {{ job.tenant || 'pool' }}
                <span v-if="!shows('step')">· {{ job.step || 'not started' }}</span>
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('step')">
            <span class="truncate text-p-sm text-ink-gray-6">
              {{ job.step || 'not started' }}
            </span>
          </ListCell>
          <ListCell v-if="shows('attempts')">
            <span class="text-p-sm tabular-nums text-ink-gray-5">
              {{ job.attempts > 1 ? `${job.attempts} attempts` : '' }}
            </span>
          </ListCell>
          <ListCell>
            <Tooltip v-if="job.last_error" :text="job.last_error">
              <Badge theme="red" :label="job.state" variant="subtle" />
            </Tooltip>
            <Badge v-else :theme="theme(job.state)" :label="job.state" variant="subtle" />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Badge, Tooltip,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { useListColumns } from '../lib/list'
import { useDocList } from '../lib/api'

const { visible, columns, shows } = useListColumns([
  { key: 'job', header: 'Job', track: 'minmax(0,1fr)' },
  { key: 'step', header: 'Step', track: '14rem', mobile: false },
  { key: 'attempts', header: 'Attempts', track: '8rem', mobile: false },
  { key: 'state', header: 'State', track: '9rem', mobile: '6rem' },
])

const resource = useDocList('Provisioning Job', {
  fields: ['name', 'tenant', 'action', 'state', 'step', 'attempts', 'last_error'],
  orderBy: 'creation desc',
  limit: 30,
})

const rows = computed(() => resource.data || [])

const theme = (state) =>
  ({
    Succeeded: 'green',
    Failed: 'red',
    Running: 'blue',
    'Awaiting Agent': 'blue',
    Bootstrapping: 'blue',
  })[state] || 'gray'
</script>

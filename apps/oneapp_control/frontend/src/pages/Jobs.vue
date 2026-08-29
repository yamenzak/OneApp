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

    <List v-else :columns="COLUMNS" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in HEADERS" :key="c" :label="c" />
      </ListHeader>

      <ListRows :items="rows" row-key="name" v-slot="{ item: job }">
        <ListRow>
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ job.action }}</p>
              <p class="truncate text-xs text-ink-gray-5">{{ job.tenant || 'pool' }}</p>
            </div>
          </ListCell>
          <ListCell>
            <span class="truncate text-p-sm text-ink-gray-6">
              {{ job.step || 'not started' }}
            </span>
          </ListCell>
          <ListCell>
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
import { useList } from '../lib/api'

const COLUMNS = ['minmax(0,1fr)', '14rem', '8rem', '9rem']
const HEADERS = ['Job', 'Step', 'Attempts', 'State']

const resource = useList('Provisioning Job', {
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

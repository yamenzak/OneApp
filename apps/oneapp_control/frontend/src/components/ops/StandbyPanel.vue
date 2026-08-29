<template>
  <div>
    <p class="mb-4 text-p-base text-ink-gray-6">
      Warm sites, created ahead of demand so a signup does not wait several
      minutes for Frappe Cloud. An empty pool is a slow signup; a stuck one is a
      site nobody will ever claim.
    </p>

    <div v-if="loading && !rows.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!rows.length"
      title="No warm sites"
      description="Set a standby target on a shard and the pool fills on the next cron. Signup falls back to creating on demand until then."
    />

    <List v-else :columns="columns" :row-height="52" class="list-row-px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
        <ListRow :value="value">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ row.press_site || row.name }}</p>
              <p class="truncate text-xs text-ink-gray-5">
                {{ row.shard }}
                <span v-if="!shows('claimed') && row.claimed_by">· {{ row.claimed_by }}</span>
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('claimed')">
            <span class="truncate text-p-sm text-ink-gray-6">{{ row.claimed_by || '—' }}</span>
          </ListCell>
          <ListCell>
            <Tooltip v-if="row.last_error" :text="row.last_error">
              <Badge theme="red" :label="row.status" variant="subtle" />
            </Tooltip>
            <Badge v-else :theme="theme(row.status)" :label="row.status" variant="subtle" />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  Badge, LoadingIndicator, Tooltip,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { useListColumns } from '../../lib/list'
import { api } from '../../lib/api'

const rows = ref([])
const loading = ref(false)

const { visible, columns, shows } = useListColumns([
  { key: 'site', header: 'Site', track: 'minmax(0,1fr)' },
  { key: 'claimed', header: 'Claimed by', track: '12rem', mobile: false },
  { key: 'status', header: 'Status', track: '8rem', mobile: '6rem' },
])

const load = async () => {
  loading.value = true
  try {
    rows.value = (await api.standbyPool()) || []
  } finally {
    loading.value = false
  }
}

defineExpose({ reload: load, loading })
onMounted(load)

const theme = (status) =>
  ({ Ready: 'green', Claimed: 'blue', Provisioning: 'blue', Failed: 'red' })[status] || 'gray'
</script>

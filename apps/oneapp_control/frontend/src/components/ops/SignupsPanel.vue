<template>
  <div>
    <p class="mb-4 text-p-base text-ink-gray-6">
      Every signup, paid or not. One that took payment and then failed to
      provision is invisible anywhere else: the customer has been charged and
      there is no workspace to show them.
    </p>

    <div v-if="loading && !rows.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!rows.length"
      title="No signups yet"
      description="They appear here the moment someone starts checkout, before any payment."
    />

    <List v-else :columns="columns" :row-height="56" class="list-row-px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
        <ListRow :value="value" @click="row.tenant && open(row)">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">
                {{ row.workspace_name || row.requested_slug || row.email }}
              </p>
              <p class="truncate text-xs text-ink-gray-5">
                {{ row.email }}
                <span v-if="!shows('plan')">· {{ row.plan || 'no plan' }}</span>
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('plan')">
            <span class="truncate text-p-sm text-ink-gray-6">{{ row.plan || '—' }}</span>
          </ListCell>
          <ListCell v-if="shows('when')">
            <span class="text-p-sm text-ink-gray-5">{{ when(row.creation) }}</span>
          </ListCell>
          <ListCell>
            <Tooltip v-if="row.failure_reason" :text="row.failure_reason">
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Badge, LoadingIndicator, Tooltip,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell, dayjsLocal,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { useListColumns } from '../../lib/list'
import { api } from '../../lib/api'

const router = useRouter()
const rows = ref([])
const loading = ref(false)

const { visible, columns, shows } = useListColumns([
  { key: 'who', header: 'Signup', track: 'minmax(0,1fr)' },
  { key: 'plan', header: 'Plan', track: '10rem', mobile: false },
  { key: 'when', header: 'Started', track: '10rem', mobile: false },
  { key: 'status', header: 'Status', track: '8rem', mobile: '6rem' },
])

const load = async () => {
  loading.value = true
  try {
    rows.value = (await api.signups()) || []
  } finally {
    loading.value = false
  }
}

defineExpose({ reload: load, loading })
onMounted(load)

// Stored naive in the site's timezone, so a bare Date() would read it as the
// browser's and shift it.
const when = (value) => (value ? dayjsLocal(value).format('D MMM, HH:mm') : '—')

const open = (row) => router.push({ name: 'Tenant', params: { name: row.tenant } })

const theme = (status) =>
  ({
    Completed: 'green',
    Paid: 'blue',
    Provisioning: 'blue',
    Failed: 'red',
    Cancelled: 'gray',
  })[status] || 'gray'
</script>

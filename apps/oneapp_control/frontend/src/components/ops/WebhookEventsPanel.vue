<template>
  <div>
    <p class="mb-4 text-p-base text-ink-gray-6">
      The webhook answers Stripe 200 even when a handler raises, because Stripe
      would otherwise retry a bug forever. The row is what you replay from once
      it is fixed — which only works if the rows are somewhere you can see them.
    </p>

    <div class="mb-3">
      <TabButtons v-model="filter" :options="FILTERS" />
    </div>

    <div v-if="loading && !rows.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!rows.length"
      title="Nothing here"
      :description="filter === 'Failed'
        ? 'No Stripe event has failed a handler.'
        : 'Stripe events appear here as they arrive.'"
    />

    <List v-else :columns="columns" :row-height="52" class="list-row-px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
        <ListRow :value="value">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ row.event_type }}</p>
              <p class="truncate text-xs text-ink-gray-5">
                {{ row.tenant || row.event_id }}
                <span v-if="!shows('when')">· {{ when(row.creation) }}</span>
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('when')">
            <span class="text-p-sm text-ink-gray-5">{{ when(row.creation) }}</span>
          </ListCell>
          <ListCell>
            <Tooltip v-if="row.error" :text="row.error">
              <Badge theme="red" :label="row.status" variant="subtle" />
            </Tooltip>
            <Badge v-else :theme="theme(row.status)" :label="row.status" variant="subtle" />
          </ListCell>
          <ListCell class="justify-end">
            <!-- Replay is safe by the same argument the handlers already rely
                 on: a replayed invoice does not grant credits twice. -->
            <Button
              v-if="row.status === 'Failed'"
              :icon="shows('when') ? undefined : 'lucide-rotate-ccw'"
              label="Replay"
              :loading="busy === row.name"
              @click="replay(row)"
            />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  Badge, Button, LoadingIndicator, TabButtons, Tooltip,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell, dayjsLocal,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { useListColumns } from '../../lib/list'
import { api } from '../../lib/api'

const FILTERS = [
  { label: 'Failed', value: 'Failed' },
  { label: 'All', value: '' },
]

const filter = ref('Failed')
const rows = ref([])
const loading = ref(false)
const busy = ref('')

const { visible, columns, shows } = useListColumns([
  { key: 'event', header: 'Event', track: 'minmax(0,1fr)' },
  { key: 'when', header: 'Received', track: '10rem', mobile: false },
  { key: 'status', header: 'Status', track: '8rem', mobile: '6rem' },
  { key: 'action', header: '', track: '7rem', mobile: '2.5rem' },
])

const load = async () => {
  loading.value = true
  try {
    rows.value = (await api.webhookEvents(filter.value || undefined)) || []
  } finally {
    loading.value = false
  }
}

defineExpose({ reload: load, loading })
onMounted(load)
watch(filter, load)

const when = (value) => (value ? dayjsLocal(value).format('D MMM, HH:mm') : '—')

const theme = (status) =>
  ({ Processed: 'green', Failed: 'red', Ignored: 'gray', Received: 'blue' })[status] || 'gray'

async function replay(row) {
  busy.value = row.name
  try {
    await api.replayWebhook(row.name)
    await load()
  } finally {
    busy.value = ''
  }
}
</script>

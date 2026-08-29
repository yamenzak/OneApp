<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: 'Shards' }]" />
  
    <div class="flex items-center gap-2">
      <Button label="Push config to all" :loading="pushing" @click="pushAll" />
      <Button variant="solid" label="Register server" @click="showNew = true" />
</div>
  </PageHeader>

  <div class="p-5">
    <p class="mb-4 text-p-base text-ink-gray-6">
      Where tenant sites live. Capacity is bounded by MariaDB rather than by anything
      Frappe Cloud bills, so these numbers are the ones to watch.
    </p>

    <EmptyState
      v-if="!shards.length"
      title="No shards"
      description="Provisioning refuses until one exists with headroom — a tenant placed nowhere is worse than a clear error."
    />

    <List v-else :columns="columns" :row-height="56" class="list-row-px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="shards" row-key="name" v-slot="{ item: shard, value }">
        <ListRow :value="value">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ shard.name }}</p>
              <!-- Occupancy is a column of its own where there is room, and
                   part of the subtitle where there is not: whether a shard has
                   headroom is the reason to look at this list. -->
              <p class="truncate text-xs text-ink-gray-5">
                {{ shard.press_release_group }}
                <span v-if="!shows('capacity')" class="tabular-nums">
                  · {{ shard.tenant_count }} / {{ shard.capacity_tenants || '∞' }}
                </span>
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('ring')">
            <Badge :label="shard.deploy_ring" variant="subtle" theme="gray" />
          </ListCell>
          <ListCell v-if="shows('capacity')">
            <div class="w-full">
              <div class="flex items-baseline justify-between text-xs text-ink-gray-5">
                <span class="tabular-nums">
                  {{ shard.tenant_count }} / {{ shard.capacity_tenants || '∞' }}
                </span>
                <span v-if="shard.utilisation !== null" class="tabular-nums">
                  {{ Math.round(shard.utilisation * 100) }}%
                </span>
              </div>
              <Progress
                v-if="shard.capacity_tenants"
                class="mt-1"
                size="sm"
                :value="Math.min((shard.utilisation || 0) * 100, 100)"
              />
            </div>
          </ListCell>
          <ListCell>
            <Badge
              :theme="shard.accepts_new_tenants ? 'green' : 'gray'"
              :label="shard.accepts_new_tenants ? 'Accepting' : 'Closed'"
              variant="subtle"
            />
          </ListCell>
          <ListCell>
            <!-- The action stays reachable on a phone; only its label goes.
                 `label` is still the accessible name and the tooltip. -->
            <Button
              v-if="isMobile"
              icon="lucide-upload"
              label="Push config"
              @click.stop="api.pushBenchConfig(shard.name)"
            />
            <Button v-else label="Push config" @click.stop="api.pushBenchConfig(shard.name)" />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>

  <NewShardDialog v-model="showNew" @created="load" />
</template>

<script setup>
import { onMounted, ref } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Badge, Progress,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import NewShardDialog from '../components/NewShardDialog.vue'
import { useListColumns } from '../lib/list'
import { useIsMobile } from '../lib/screen'
import { api } from '../lib/api'

const isMobile = useIsMobile()

const { visible, columns, shows } = useListColumns([
  { key: 'shard', header: 'Shard', track: 'minmax(0,1fr)' },
  { key: 'ring', header: 'Ring', track: '7rem', mobile: false },
  { key: 'capacity', header: 'Capacity', track: '12rem', mobile: false },
  { key: 'intake', header: 'Intake', track: '8rem', mobile: '5.5rem' },
  { key: 'action', header: '', track: '9rem', mobile: '2.5rem' },
])

const shards = ref([])
const pushing = ref(false)
const showNew = ref(false)

const load = async () => (shards.value = (await api.shards()) || [])

async function pushAll() {
  pushing.value = true
  try {
    await api.pushBenchConfigAll()
    await load()
  } finally {
    pushing.value = false
  }
}

onMounted(load)
</script>

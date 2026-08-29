<template>
  <div class="mx-auto max-w-5xl p-8">
    <PageHeader>
      <template #title><h1 class="text-xl font-semibold">Shards</h1></template>
      <template #actions>
        <Button label="Push config to all" :loading="pushing" @click="pushAll" />
      </template>
    </PageHeader>

    <p class="mt-1 text-p-base text-ink-gray-6">
      Where tenant sites live. Capacity is bounded by MariaDB, not by anything
      Frappe Cloud bills — see docs/ARCHITECTURE.md §1.
    </p>

    <div class="mt-6 divide-y divide-outline-gray-1 rounded border border-outline-gray-2">
      <div v-for="shard in shards" :key="shard.name" class="p-3">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-p-base font-medium">{{ shard.name }}</p>
            <p class="truncate text-p-sm text-ink-gray-5">
              {{ shard.press_release_group }} · {{ shard.deploy_ring }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-3">
            <span class="text-p-sm tabular-nums text-ink-gray-6">
              {{ shard.tenant_count }} / {{ shard.capacity_tenants || '∞' }}
            </span>
            <Badge
              :theme="shard.accepts_new_tenants ? 'green' : 'gray'"
              :label="shard.accepts_new_tenants ? 'Accepting' : 'Closed'"
            />
            <Button label="Push config" @click="push(shard.name)" />
          </div>
        </div>
        <Progress
          v-if="shard.capacity_tenants"
          class="mt-2"
          :value="(shard.tenant_count / shard.capacity_tenants) * 100"
          size="sm"
        />
      </div>
      <p v-if="!shards.length" class="p-6 text-center text-p-sm text-ink-gray-5">
        No shards. Provisioning refuses until one exists with headroom.
      </p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { PageHeader, Button, Badge, Progress } from '@/ui'
import { api } from '../lib/api'

const shards = ref([])
const pushing = ref(false)

async function load() {
  shards.value = await api.shards()
}

// Both already toast their outcome through the shared layer.
const push = (name) => api.pushBenchConfig(name)

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

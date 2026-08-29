<template>
  <div class="mx-auto max-w-5xl p-8">
    <PageHeader>
      <template #title><h1 class="text-xl font-semibold">Tenants</h1></template>
      <template #actions>
        <Button variant="solid" label="New tenant" @click="showCreate = true" />
      </template>
    </PageHeader>

    <div v-if="tenants.loading && !rows.length" class="mt-8 grid place-items-center">
      <LoadingIndicator class="h-5 w-5 text-ink-gray-5" />
    </div>

    <div
      v-else-if="!rows.length"
      class="mt-8 rounded border border-dashed border-outline-gray-2 p-10 text-center"
    >
      <p class="text-p-base font-medium">No tenants yet</p>
      <p class="mt-1 text-p-sm text-ink-gray-6">
        Creating one provisions a real site on Frappe Cloud.
      </p>
    </div>

    <div v-else class="mt-6 divide-y divide-outline-gray-1 rounded border border-outline-gray-2">
      <router-link
        v-for="tenant in rows"
        :key="tenant.name"
        :to="`/tenants/${tenant.name}`"
        class="flex items-center justify-between p-3 hover:bg-surface-gray-1"
      >
        <div class="min-w-0">
          <p class="truncate text-p-base font-medium">{{ tenant.tenant_name }}</p>
          <p class="truncate text-p-sm text-ink-gray-5">
            {{ tenant.site_name || tenant.tenant_slug }}
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-3">
          <span class="text-p-sm text-ink-gray-5">{{ tenant.plan || '—' }}</span>
          <Badge :theme="statusTheme(tenant.status)" :label="tenant.status" />
        </div>
      </router-link>
    </div>

    <CreateTenantDialog v-model="showCreate" @created="tenants.reload()" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { PageHeader, Button, Badge, LoadingIndicator } from '@/ui'
import CreateTenantDialog from '../components/CreateTenantDialog.vue'
import { useList } from '../lib/api'

// Live: the socket refetches this whenever any Tenant changes, so a site that
// finishes provisioning appears without anyone reloading.
const tenants = useList('Tenant', {
  fields: ['name', 'tenant_name', 'tenant_slug', 'status', 'plan', 'site_name'],
  orderBy: 'creation desc',
})

const rows = computed(() => tenants.data || [])
const showCreate = ref(false)

const statusTheme = (status) =>
  ({
    Active: 'green',
    Provisioning: 'blue',
    Suspended: 'orange',
    Failed: 'red',
    Archived: 'gray',
  })[status] || 'gray'
</script>

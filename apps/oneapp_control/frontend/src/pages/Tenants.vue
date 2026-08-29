<template>
  <PageHeader>
    <template #title>
      <Breadcrumbs :items="[{ label: 'Tenants' }]" />
    </template>
    <template #actions>
      <Button
        variant="solid"
        label="New tenant"
        :disabled="!setup.canProvision"
        @click="showCreate = true"
      />
    </template>
  </PageHeader>

  <div class="p-5">
    <Alert v-if="!setup.canProvision" variant="warning" title="Setup incomplete" class="mb-4">
      Provisioning is disabled until the required configuration is in place.
      <template #actions>
        <Button label="Open setup" @click="$router.push({ name: 'Setup' })" />
      </template>
    </Alert>

    <div v-if="resource.loading && !rows.length" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!rows.length"
      title="No tenants yet"
      description="Creating one provisions a real site on Frappe Cloud. It takes a few minutes unless a warm site is waiting."
    />

    <List v-else :columns="COLUMNS" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in HEADERS" :key="c" :label="c" />
      </ListHeader>

      <ListRows :items="rows" v-slot="{ item: tenant }">
        <ListRow
          :row-key="tenant.name"
          @click="$router.push({ name: 'Tenant', params: { name: tenant.name } })"
        >
          <ListCell>
            <div class="flex min-w-0 items-center gap-2.5">
              <Avatar :label="tenant.tenant_name" size="sm" shape="square" />
              <div class="min-w-0">
                <p class="truncate text-base text-ink-gray-8">{{ tenant.tenant_name }}</p>
                <p class="truncate text-xs text-ink-gray-5">
                  {{ tenant.site_name || `${tenant.tenant_slug}.4dl.app` }}
                </p>
              </div>
            </div>
          </ListCell>
          <ListCell>
            <span class="text-p-sm text-ink-gray-6">{{ tenant.plan || '—' }}</span>
          </ListCell>
          <ListCell>
            <Badge :theme="statusTheme(tenant.status)" :label="tenant.status" variant="subtle" />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>

  <CreateTenantDialog v-model="showCreate" @created="resource.reload()" />
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Badge, Avatar, Alert, LoadingIndicator,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import CreateTenantDialog from '../components/CreateTenantDialog.vue'
import { useList } from '../lib/api'
import { setup } from '../lib/setup'

// Deterministic tracks: `auto` sizes independently per row and the columns
// would not line up.
const COLUMNS = ['minmax(0,1fr)', '10rem', '8rem']
const HEADERS = ['Workspace', 'Plan', 'Status']

// Live over the socket: a site that finishes provisioning appears on its own.
const resource = useList('Tenant', {
  fields: ['name', 'tenant_name', 'tenant_slug', 'status', 'plan', 'site_name'],
  orderBy: 'creation desc',
})

const rows = computed(() => resource.data || [])
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

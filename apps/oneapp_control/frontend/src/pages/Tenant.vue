<template>
  <PageHeader>
    <Breadcrumbs
      :items="[
        { label: 'Tenants', route: { path: '/tenants' } },
        { label: tenant?.tenant_name || name },
      ]"
    />
  
    <div class="flex items-center gap-2">
      <Button
        v-if="tenant?.status === 'Active'"
        label="Suspend"
        @click="act('suspend')"
      />
      <Button
        v-else-if="tenant?.status === 'Suspended'"
        variant="solid"
        label="Resume"
        @click="act('resume')"
      />
      <Button
        v-else-if="tenant?.status === 'Failed'"
        variant="solid"
        label="Retry provisioning"
        @click="act('provision')"
      />
</div>
  </PageHeader>

  <div v-if="tenant" class="mx-auto max-w-3xl p-5">
    <Alert
      v-if="tenant.status === 'Failed'"
      theme="red"
      title="Provisioning failed"
      class="mb-5"
    >
      <template #description>
        {{ tenant.suspended_reason || 'See the provisioning job for the reason.' }}
      </template>
    </Alert>

    <List :columns="['12rem', 'minmax(0,1fr)']" divider="full">
      <ListRows :items="rows" row-key="label" v-slot="{ item: row, value }">
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
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Alert,
  List, ListRows, ListRow, ListCell,
} from '@/ui'
import { api, useDocument } from '../lib/api'

const props = defineProps({ name: { type: String, required: true } })

// Live: a status change from the provisioning worker lands here on its own.
const resource = useDocument('Tenant', () => props.name)
const tenant = computed(() => resource.data)

const rows = computed(() => {
  const t = tenant.value
  if (!t) return []
  return [
    { label: 'Status', value: t.status },
    { label: 'Site', value: t.site_name || '—' },
    { label: 'Custom domain', value: t.primary_domain || '—' },
    { label: 'Plan', value: t.plan || '—' },
    { label: 'Shard', value: t.shard || '—' },
    { label: 'Owner', value: t.owner_email },
    { label: 'Users', value: `${t.user_count || 0} of ${t.max_users || '—'}` },
  ]
})

// api.* already toasts success and renders parsed Frappe errors.
async function act(kind) {
  if (kind === 'suspend') await api.suspend(props.name, 'Suspended by operator')
  if (kind === 'resume') await api.resume(props.name)
  if (kind === 'provision') await api.provision(props.name)
  resource.reload()
}
</script>

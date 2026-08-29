<template>
  <PageHeader>
    <template #title>
      <Breadcrumbs
        :items="[
          { label: 'Tenants', route: { path: '/tenants' } },
          { label: tenant?.tenant_name || name },
        ]"
      />
    </template>
    <template #actions>
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
    </template>
  </PageHeader>

  <div v-if="tenant" class="mx-auto max-w-3xl p-5">
    <Alert
      v-if="tenant.status === 'Failed'"
      variant="error"
      title="Provisioning failed"
      class="mb-5"
    >
      {{ tenant.suspended_reason || 'See the provisioning job for the reason.' }}
    </Alert>

    <List :columns="['12rem', 'minmax(0,1fr)']" divider="full">
      <ListRows :items="rows" v-slot="{ item: row }">
        <ListRow :row-key="row.label">
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

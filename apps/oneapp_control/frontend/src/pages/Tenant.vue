<template>
  <div class="mx-auto max-w-3xl p-8">
    <Breadcrumbs
      :items="[{ label: 'Tenants', route: '/tenants' }, { label: tenant?.tenant_name || name }]"
    />

    <PageHeader class="mt-3">
      <template #title>
        <h1 class="text-xl font-semibold">{{ tenant?.tenant_name || name }}</h1>
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

    <dl
      v-if="tenant"
      class="mt-6 divide-y divide-outline-gray-1 rounded border border-outline-gray-2"
    >
      <div v-for="row in rows" :key="row.label" class="flex justify-between gap-4 p-3">
        <dt class="text-p-sm text-ink-gray-6">{{ row.label }}</dt>
        <dd class="truncate text-p-sm font-medium">{{ row.value }}</dd>
      </div>
    </dl>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Breadcrumbs, PageHeader, Button } from '@/ui'
import { api, useDocument } from '../lib/api'

const props = defineProps({ name: { type: String, required: true } })

// Live document: a status change from the provisioning worker lands here.
const resource = useDocument('Tenant', () => props.name)
const tenant = computed(() => resource.data)

const rows = computed(() => [
  { label: 'Status', value: tenant.value.status },
  { label: 'Site', value: tenant.value.site_name || '—' },
  { label: 'Custom domain', value: tenant.value.primary_domain || '—' },
  { label: 'Plan', value: tenant.value.plan || '—' },
  { label: 'Shard', value: tenant.value.shard || '—' },
  { label: 'Owner', value: tenant.value.owner_email },
  { label: 'Users', value: `${tenant.value.user_count || 0} / ${tenant.value.max_users || '—'}` },
])

// api.* already toasts success and renders parsed Frappe errors.
async function act(kind) {
  if (kind === 'suspend') await api.suspend(props.name, 'Suspended by operator')
  if (kind === 'resume') await api.resume(props.name)
  if (kind === 'provision') await api.provision(props.name)
  resource.reload()
}
</script>

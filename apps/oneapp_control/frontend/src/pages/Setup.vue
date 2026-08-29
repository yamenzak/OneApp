<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: 'Setup' }]" />
  
    <div class="flex items-center gap-2">
      <Button :loading="setup.loading" label="Re-check" @click="setup.load()" />
      <Button variant="solid" label="Open settings" @click="openSettings()" />
</div>
  </PageHeader>

  <div class="mx-auto max-w-3xl p-5">
    <Alert
      v-if="setup.canProvision"
      theme="green"
      title="Ready to provision"
      class="mb-6"
    >
      <template #description>
        Anything outstanding below limits what tenants can do, not whether they come up.
      </template>
    </Alert>
    <Alert v-else theme="amber" title="Provisioning is disabled" class="mb-6">
      <template #description>
        A half-configured control plane fails partway through provisioning, with a real
        site already created. The required items below have to be set first.
      </template>
    </Alert>

    <section v-for="group in GROUPS" :key="group.key" class="mb-8">
      <div class="mb-1 flex items-baseline justify-between">
        <h2 class="text-base font-medium text-ink-gray-8">{{ group.label }}</h2>
        <span class="text-p-sm tabular-nums text-ink-gray-5">
          {{ done(group.key) }} of {{ setup.group(group.key).length }}
        </span>
      </div>
      <p class="mb-3 text-p-sm text-ink-gray-5">{{ group.blurb }}</p>

      <List :columns="['5.5rem', 'minmax(0,1fr)']" divider="full">
        <ListRows :items="setup.group(group.key)" row-key="key" v-slot="{ item: check }">
          <ListRow>
            <ListCell>
              <Badge
                :theme="check.ok ? 'green' : group.key === 'blocking' ? 'red' : 'gray'"
                :label="check.ok ? 'Set' : 'Missing'"
                variant="subtle"
              />
            </ListCell>
            <ListCell>
              <div class="min-w-0 py-0.5">
                <p class="text-base text-ink-gray-8">{{ check.label }}</p>
                <p class="mt-0.5 text-p-sm text-ink-gray-6">{{ check.detail }}</p>
                <p class="mt-1 text-xs text-ink-gray-4">{{ check.where }}</p>
              </div>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Alert, Badge,
  List, ListRows, ListRow, ListCell,
} from '@/ui'
import { setup } from '../lib/setup'
import { openSettings } from '../lib/settings'

const GROUPS = [
  {
    key: 'blocking',
    label: 'Required',
    blurb: 'Without these, provisioning fails partway and leaves a real site behind.',
  },
  {
    key: 'billing',
    label: 'Billing',
    blurb: 'Tenants can be created without these, but nobody can pay you.',
  },
  {
    key: 'optional',
    label: 'Tenant features',
    blurb: 'Each is a capability tenants gain. Sites work without them.',
  },
]

const done = (key) => setup.group(key).filter((c) => c.ok).length

onMounted(() => setup.load())
</script>

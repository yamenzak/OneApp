<template>
  <div class="mx-auto max-w-3xl p-8">
    <PageHeader>
      <template #title>
        <h1 class="text-xl font-semibold">Setup</h1>
      </template>
      <template #actions>
        <Button :loading="setup.loading" label="Re-check" @click="setup.load()" />
      </template>
    </PageHeader>

    <p class="mt-1 text-p-base text-ink-gray-6">
      Provisioning stays disabled until the required items are configured. Each one
      says where to set it.
    </p>

    <Alert
      v-if="setup.canProvision"
      class="mt-6"
      variant="success"
      title="Ready to provision"
    >
      Tenants can be created. Anything still outstanding below limits what those
      tenants can do, not whether they come up.
    </Alert>

    <div v-for="group in groups" :key="group.key" class="mt-8">
      <div class="flex items-baseline justify-between">
        <h2 class="text-base font-medium">{{ group.label }}</h2>
        <span class="text-sm tabular-nums text-ink-gray-5">
          {{ done(group.key) }} / {{ setup.group(group.key).length }}
        </span>
      </div>
      <p class="mt-0.5 text-p-sm text-ink-gray-5">{{ group.blurb }}</p>

      <div class="mt-3 divide-y divide-outline-gray-1 rounded border border-outline-gray-2">
        <div
          v-for="check in setup.group(group.key)"
          :key="check.key"
          class="flex gap-3 p-3"
        >
          <Badge
            :theme="check.ok ? 'green' : group.key === 'blocking' ? 'red' : 'gray'"
            :label="check.ok ? 'Set' : 'Missing'"
            class="mt-0.5 shrink-0"
          />
          <div class="min-w-0">
            <p class="text-p-base font-medium">{{ check.label }}</p>
            <p class="mt-0.5 text-p-sm text-ink-gray-6">{{ check.detail }}</p>
            <p class="mt-1 text-p-sm text-ink-gray-4">{{ check.where }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { PageHeader, Button, Alert, Badge } from '@/ui'
import { setup } from '../lib/setup'

const groups = [
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
    blurb: 'Each one is a capability tenants gain. Sites work without them.',
  },
]

const done = (key) => setup.group(key).filter((c) => c.ok).length

onMounted(() => setup.load())
</script>

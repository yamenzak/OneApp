<template>
  <!--
    Configuration readiness — a checklist with blockers, not records, which is
    why it is a `component` screen rather than a list. The manifest is a
    shortcut, not a cage.

    No PageHeader: a screen renders inside the shell's own header, which the
    space and screen already fill. The re-check button lives with the content.
  -->
  <div class="mx-auto max-w-3xl p-5">
    <div class="mb-6 flex items-start justify-between gap-3">
      <Alert
        v-if="readiness.canProvision"
        theme="green"
        title="Ready to provision"
        class="flex-1"
      >
        <template #description>
          Anything outstanding below limits what tenants can do, not whether they come up.
        </template>
      </Alert>
      <Alert v-else theme="amber" title="Provisioning is disabled" class="flex-1">
        <template #description>
          A half-configured control plane fails partway, with a real site already created.
        </template>
      </Alert>

      <!-- An icon, not the word "Re-check": `label` stays as the accessible
           name and the tooltip. -->
      <Button
        variant="ghost"
        icon="lucide-refresh-cw"
        label="Re-check"
        tooltip="Re-check"
        :loading="readiness.loading"
        @click="readiness.load()"
      />
    </div>

    <section v-for="group in GROUPS" :key="group.key" class="mb-8">
      <div class="mb-1 flex items-baseline justify-between">
        <h2 class="text-base-medium text-ink-gray-8">{{ group.label }}</h2>
        <span class="text-p-sm tabular-nums text-ink-gray-5">
          {{ done(group.key) }} of {{ readiness.group(group.key).length }}
        </span>
      </div>
      <p class="mb-3 text-p-sm text-ink-gray-5">{{ group.blurb }}</p>

      <!-- Name first, status trailing — the opposite indents every label
           behind a stack of identical pills, so the eye lands on a repeated
           word rather than on which check this is. -->
      <List :columns="['minmax(0,1fr)', '5.5rem']" divider="full">
        <ListRows
          :items="readiness.group(group.key)"
          row-key="key"
          v-slot="{ item: check, value }"
        >
          <ListRow :value="value" class="py-3">
            <ListCell>
              <!-- A satisfied check is a name and a tick. What it is for and
                   where to put it are only worth the space while it is
                   missing. -->
              <div class="min-w-0 py-0.5">
                <p class="text-base text-ink-gray-8">{{ check.label }}</p>
                <div v-if="!check.ok" class="mt-1 space-y-1">
                  <p class="text-p-sm text-ink-gray-6">{{ check.detail }}</p>
                  <p class="text-p-sm text-ink-gray-7">{{ check.needs }}</p>
                  <p class="text-xs text-ink-gray-4">{{ check.where }}</p>
                </div>
              </div>
            </ListCell>
            <ListCell class="items-start justify-end pt-0.5">
              <Badge
                :theme="check.ok ? 'green' : group.key === 'blocking' ? 'red' : 'gray'"
                :label="check.ok ? 'Set' : 'Missing'"
                variant="subtle"
              />
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { Alert, Badge, Button, List, ListRows, ListRow, ListCell } from '@/ui'
import { readiness } from './readiness'

// Every screen component takes these, whether or not it reads them.
defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

const GROUPS = [
  {
    key: 'blocking',
    label: 'Required',
    blurb: 'Provisioning is refused until all of these pass.',
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

const done = (key) => readiness.group(key).filter((c) => c.ok).length

onMounted(() => readiness.load())
</script>

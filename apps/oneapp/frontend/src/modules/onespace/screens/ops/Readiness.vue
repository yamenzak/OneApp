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
        :title="__('Ready to provision')"
        class="flex-1"
      >
        <template #description>
          {{ __('Anything outstanding below limits what tenants can do, not whether they come up.') }}
        </template>
      </Alert>
      <Alert v-else theme="amber" :title="__('Provisioning is disabled')" class="flex-1">
        <template #description>
          {{ __('A half-configured control plane fails partway, with a real site already created.') }}
        </template>
      </Alert>

      <div class="flex shrink-0 items-center gap-2">
        <!--
          The one thing on this page that *changes* something. Everything else
          here reads state; this creates the KV namespace, uploads the inbound
          worker, turns Email Routing on and points the catch-all at it. Safe
          to press again — every step finds what is already there — which is
          why it is a button beside a checklist rather than a wizard.
        -->
        <Button
          icon-left="lucide-mail-check"
          :label="__('Bring up mail')"
          :tooltip="__('Create the KV namespace, deploy the inbound worker, and turn Email Routing on')"
          :loading="bringingUp"
          @click="bringUp"
        />
        <!-- An icon, not the word "Re-check": `label` stays as the accessible
             name and the tooltip. -->
        <Button
          variant="ghost"
          icon="lucide-refresh-cw"
          :label="__('Re-check')"
          :tooltip="__('Re-check')"
          :loading="readiness.loading"
          @click="readiness.load()"
        />
      </div>
    </div>

    <!-- What the bring-up did, step by step. Kept on screen rather than
         thrown as a toast: four steps with one cross in the middle is a thing
         to read, not a thing to catch. -->
    <section v-if="steps.length" class="mb-8">
      <h2 class="mb-2 text-base-medium text-ink-primary">{{ __('Mail bring-up') }}</h2>
      <List :columns="['minmax(0,1fr)', '5.5rem']" divider="full">
        <ListRows :items="steps" row-key="label" v-slot="{ item: step, value }">
          <ListRow :value="value" class="py-3">
            <ListCell>
              <p class="text-p-base text-ink-primary">{{ step.label }}</p>
              <p class="text-p-sm text-ink-muted">{{ step.detail }}</p>
            </ListCell>
            <ListCell>
              <Badge :theme="step.ok ? 'green' : 'amber'"
                     :label="step.ok ? __('Done') : __('Left')" />
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>

    <section v-for="group in GROUPS" :key="group.key" class="mb-8">
      <div class="mb-1 flex items-baseline justify-between">
        <h2 class="text-base-medium text-ink-primary">{{ group.label }}</h2>
        <span class="text-p-sm tabular-nums text-ink-muted">
          {{ __('{0} of {1}', [done(group.key), readiness.group(group.key).length]) }}
        </span>
      </div>
      <p class="mb-3 text-p-sm text-ink-muted">{{ group.blurb }}</p>

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
                <p class="text-base text-ink-primary">{{ check.label }}</p>
                <div v-if="!check.ok" class="mt-1 space-y-1">
                  <p class="text-p-sm text-ink-secondary">{{ check.detail }}</p>
                  <p class="text-p-sm text-ink-secondary">{{ check.needs }}</p>
                  <p class="text-xs text-ink-gray-4">{{ check.where }}</p>
                </div>
              </div>
            </ListCell>
            <ListCell class="items-start justify-end pt-0.5">
              <Badge
                :theme="check.ok ? 'green' : group.key === 'blocking' ? 'red' : 'gray'"
                :label="check.ok ? __('Set') : __('Missing')"
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
import { onMounted, ref } from 'vue'

import { Alert, Badge, Button, List, ListRows, ListRow, ListCell } from '@/ui'
import { callMethod } from '@/shared/lib/runtime/resource'
import { readiness } from '@/modules/onespace/screens/ops/readiness'
import { __ } from '@/shared/lib/runtime/translate'

// Every screen component takes these, whether or not it reads them.
defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// The bring-up, and what it did. `steps` stays on screen until somebody
// presses it again — a checklist that appeared and vanished would be the one
// thing on this page nobody could read twice.
const bringingUp = ref(false)
const steps = ref([])

async function bringUp() {
  bringingUp.value = true
  try {
    const answer = await callMethod('oneapp_control.api.admin.bring_up', {}, {
      success: __('Mail brought up'),
    })
    steps.value = answer?.steps || []
  } finally {
    bringingUp.value = false
    // The checks read the same state the steps just changed.
    readiness.load()
  }
}

const GROUPS = [
  {
    key: 'blocking',
    label: __('Required'),
    blurb: __('Provisioning is refused until all of these pass.'),
  },
  {
    key: 'billing',
    label: __('Billing'),
    blurb: __('Tenants can be created without these, but nobody can pay you.'),
  },
  {
    key: 'optional',
    label: __('Tenant features'),
    blurb: __('Each is a capability tenants gain. Sites work without them.'),
  },
]

const done = (key) => readiness.group(key).filter((c) => c.ok).length

onMounted(() => readiness.load())
</script>

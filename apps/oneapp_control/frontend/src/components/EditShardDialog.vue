<template>
  <Dialog v-model="open" :title="`Edit ${shard?.shard_name || 'shard'}`" size="xl">
    <div v-if="!shard" class="grid place-items-center py-10">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else class="flex flex-col gap-4">
      <!--
        Only the operating settings. The press identity — server, bench group,
        version, domain and mode — is what the tenants already here were created
        against, so editing it would leave the shard describing a machine those
        sites are not on. Replacing a shard is registering a new one and
        draining this one, which is what the intake switch below is for.
      -->
      <div class="rounded-6 bg-surface-gray-1 p-3">
        <div class="flex flex-wrap gap-x-6 gap-y-1">
          <span v-for="fact in facts" :key="fact.label" class="text-p-sm text-ink-gray-8">
            {{ fact.label }}: <span class="text-ink-gray-6">{{ fact.value }}</span>
          </span>
        </div>
        <p class="mt-1.5 text-p-sm text-ink-gray-5">
          Fixed once tenants are placed here. To move off this machine, stop
          intake below and register its replacement.
        </p>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <FormControl
          v-model="form.status"
          type="select"
          label="Status"
          :options="['Active', 'Draining', 'Full', 'Maintenance']"
        />
        <FormControl
          v-model="form.deploy_ring"
          type="select"
          label="Deploy ring"
          :options="['Canary', 'Wave 1', 'Wave 2', 'Fleet']"
          description="Migration order. Canary goes first."
        />
        <FormControl
          v-model="form.capacity_tenants"
          type="number"
          label="Soft cap (tenants)"
          :description="capacityHint"
        />
        <FormControl v-model="form.standby_target" type="number" label="Standby sites" />
        <FormControl
          v-model="form.region"
          type="select"
          label="Region"
          :options="regionOptions"
        />
        <FormControl
          v-model="form.press_site_plan"
          type="select"
          label="Default site plan"
          :options="sitePlanOptions"
        />
      </div>

      <!-- The documented way to drain a server, and until now the one thing on
           this page that needed the desk. -->
      <Switch
        v-model="form.accepts_new_tenants"
        label="Accepting new tenants"
        description="Off drains the shard: the allocator stops placing here, and the tenants already on it are untouched."
        padded
      />

      <FormControl v-model="form.notes" type="textarea" label="Notes" />

      <ErrorMessage v-if="error" :message="error" />
    </div>

    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Button, Dialog, ErrorMessage, FormControl, LoadingIndicator, Switch,
} from '@/ui'
import { api } from '../lib/api'

const props = defineProps({
  name: { type: String, default: '' },
  // Passed in rather than fetched again: the parent already loaded them for the
  // register dialog, and two reads of the same press call per page is a wasted
  // round trip against an API we deliberately give a short timeout.
  capacity: { type: Object, default: () => ({}) },
})
const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['saved'])

const shard = ref(null)
const saving = ref(false)
const error = ref('')

const form = reactive({
  status: 'Active',
  accepts_new_tenants: true,
  capacity_tenants: 30,
  deploy_ring: 'Fleet',
  standby_target: 0,
  press_site_plan: '',
  region: '',
  notes: '',
})

const facts = computed(() => {
  const s = shard.value
  if (!s) return []
  return [
    { label: 'Server', value: s.press_server || '—' },
    { label: 'Bench group', value: s.press_release_group || '—' },
    { label: 'Version', value: s.press_version || '—' },
    { label: 'Domain', value: `${s.domain} (${s.domain_mode})` },
    { label: 'Apps', value: s.site_apps || '—' },
  ]
})

const regionOptions = computed(() =>
  (props.capacity.regions || []).map((r) => ({ label: r.region_name, value: r.name })),
)
const sitePlanOptions = computed(() => [
  { label: 'Use the bench default', value: '' },
  ...(props.capacity.site_plans || []).map((p) => ({
    label: `${p.name} — $${p.price_usd}/mo`,
    value: p.name,
  })),
])

const capacityHint = computed(() => {
  const server = (props.capacity.servers || []).find(
    (s) => s.name === shard.value?.press_server,
  )
  if (!server?.recommended_capacity) return 'A soft cap. MariaDB is the real ceiling.'
  return `${server.recommended_capacity} suits this machine. Currently holding ${shard.value?.tenant_count ?? 0}.`
})

watch([open, () => props.name], async ([isOpen, name]) => {
  if (!isOpen || !name) return
  error.value = ''
  shard.value = null
  const doc = await api.shard(name)
  shard.value = doc
  for (const field of Object.keys(form)) {
    form[field] =
      field === 'accepts_new_tenants' ? Boolean(doc.accepts_new_tenants) : doc[field] ?? form[field]
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    await api.updateShard(props.name, {
      ...form,
      accepts_new_tenants: form.accepts_new_tenants ? 1 : 0,
    })
    open.value = false
    emit('saved')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}
</script>

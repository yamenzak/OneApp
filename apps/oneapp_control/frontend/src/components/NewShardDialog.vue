<template>
  <!-- Title and size are props, and the body is the default slot. The
       `:options` object and `#body-content` are frappe-ui v0 spelling: both
       are silently ignored, so the dialog opened with no heading and an
       empty body. -->
  <Dialog v-model="open" title="Register a server" size="xl">
    <div v-if="loading" class="grid place-items-center py-10">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else class="flex flex-col gap-4">
      <p class="text-p-base text-ink-gray-6">
        Buy a server on Frappe Cloud and add a bench group to it, then register
        the pair here. The allocator places new tenants on it from the next
        signup — least loaded first — and the region becomes selectable at
        signup as soon as it has headroom.
      </p>

      <!-- "Unreachable" and "you own no servers" are different problems, and
           only one of them is solved by buying a server. -->
      <Alert v-if="capacity.error" theme="amber" title="Frappe Cloud did not answer">
        <template #description>
          {{ capacity.error }} — the lists below are empty because we could not
          ask, not because there is nothing there.
        </template>
      </Alert>

      <div class="grid gap-4 sm:grid-cols-2">
        <FormControl
          v-model="form.press_server"
          type="select"
          label="Server"
          :options="serverOptions"
          :description="serverSpec"
        />
        <FormControl
          v-model="form.press_release_group"
          type="select"
          label="Bench group"
          :options="groupOptions"
          :description="groupSpec"
        />
      </div>

      <Alert v-if="alreadyUsed" theme="amber" title="Already registered">
        <template #description>
          A shard already covers that server and bench group. Two shards over one
          group would both count capacity against the same machine, so the
          allocator would overfill it.
        </template>
      </Alert>

      <div class="grid gap-4 sm:grid-cols-2">
        <FormControl v-model="form.shard_name" label="Shard name" placeholder="hetzner-nuremberg-2" />
        <FormControl v-model="form.region" type="select" label="Region" :options="regionOptions" />
        <FormControl v-model="form.domain" label="Tenant domain" placeholder="4dl.app" />
        <FormControl
          v-model="form.press_site_plan"
          type="select"
          label="Default site plan"
          :options="sitePlanOptions"
          description="What Frappe Cloud charges per site. A plan can override it."
        />
        <FormControl
          v-model="form.environment"
          type="select"
          label="Environment"
          :options="['Production', 'Staging']"
          description="Staging shards may be patched and redeployed automatically."
        />
        <FormControl
          v-model="form.capacity_tenants"
          type="number"
          label="Soft cap (tenants)"
          :description="capacityHint"
        />
        <FormControl v-model="form.standby_target" type="number" label="Standby sites" />
      </div>

      <!--
        Version and apps used to be text boxes, and both fail late and obscurely
        when wrong: a mismatched version sends press down its public marketplace
        path, and an app the bench does not carry fails at site creation. Frappe
        Cloud knows both, so neither is a question any more.
      -->
      <div class="rounded-6 bg-surface-gray-1 p-3">
        <p class="text-p-sm text-ink-gray-6">
          Read from Frappe Cloud when you pick a bench group:
        </p>
        <div class="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1">
          <span class="text-p-sm text-ink-gray-8">
            Version:
            <span class="text-ink-gray-6">{{ form.press_version || '—' }}</span>
          </span>
          <span class="text-p-sm text-ink-gray-8">
            Cluster:
            <span class="text-ink-gray-6">{{ form.press_cluster || '—' }}</span>
          </span>
          <span class="min-w-0 text-p-sm text-ink-gray-8">
            Apps:
            <span class="text-ink-gray-6">{{ form.site_apps || (appsLoading ? 'reading…' : '—') }}</span>
          </span>
        </div>
        <p v-if="appsError" class="mt-1.5 text-p-sm text-ink-amber-3">
          Could not read the bench's apps ({{ appsError }}). Register anyway and
          fix the app list on the shard, or try again.
        </p>
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button
        variant="solid"
        label="Register"
        :loading="saving"
        :disabled="!complete || alreadyUsed"
        @click="save"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Alert, Button, Dialog, ErrorMessage, FormControl, LoadingIndicator } from '@/ui'
import { api } from '../lib/api'

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['created'])

const loading = ref(false)
const saving = ref(false)
const appsLoading = ref(false)
const appsError = ref('')
const error = ref('')
const capacity = ref({ servers: [], release_groups: [], regions: [], site_plans: [], existing: [] })

const form = reactive({
  shard_name: '',
  press_server: '',
  press_release_group: '',
  press_cluster: '',
  press_site_plan: '',
  region: '',
  domain: '',
  press_version: '',
  environment: 'Production',
  capacity_tenants: 30,
  standby_target: 1,
  site_apps: '',
})

const serverOptions = computed(() =>
  capacity.value.servers.map((s) => ({
    label: `${s.title || s.name} — ${s.cluster}`,
    value: s.name,
  })),
)
const groupOptions = computed(() =>
  capacity.value.release_groups.map((g) => ({
    label: `${g.title || g.name}${g.version ? ` (${g.version})` : ''}`,
    value: g.name,
  })),
)
const regionOptions = computed(() =>
  capacity.value.regions.map((r) => ({ label: r.region_name, value: r.name })),
)
const sitePlanOptions = computed(() => [
  { label: 'Use the bench default', value: '' },
  ...(capacity.value.site_plans || []).map((p) => ({
    label: `${p.name} — $${p.price_usd}/mo`,
    value: p.name,
  })),
])

const server = computed(() =>
  capacity.value.servers.find((s) => s.name === form.press_server) || null,
)
const group = computed(() =>
  capacity.value.release_groups.find((g) => g.name === form.press_release_group) || null,
)

const serverSpec = computed(() => {
  const s = server.value
  if (!s) return 'Read live from Frappe Cloud, so the name always matches.'
  const parts = [s.instance_type, s.vcpu && `${s.vcpu} vCPU`, s.memory_gb && `${s.memory_gb} GB RAM`, s.disk_gb && `${s.disk_gb} GB disk`]
  return parts.filter(Boolean).join(' · ')
})

const groupSpec = computed(() => {
  const g = group.value
  if (!g) return ''
  return `${g.sites ?? 0} site${g.sites === 1 ? '' : 's'} · ${g.apps ?? 0} apps`
})

const capacityHint = computed(() => {
  const recommended = server.value?.recommended_capacity
  if (!recommended) return 'A soft cap. MariaDB is the real ceiling.'
  return `${recommended} suits this machine's memory and disk. A soft cap — MariaDB is the real ceiling.`
})

const alreadyUsed = computed(() =>
  (capacity.value.existing || []).some(
    ([server_, group_]) => server_ === form.press_server && group_ === form.press_release_group,
  ),
)

const complete = computed(
  () =>
    form.shard_name &&
    form.press_server &&
    form.press_release_group &&
    form.region &&
    form.domain &&
    form.press_version,
)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  error.value = ''
  try {
    capacity.value = (await api.pressCapacity()) || capacity.value
    // The tenant domain is already configured; asking again is asking someone
    // to retype a value that has one correct answer.
    if (capacity.value.tenant_domain) form.domain = capacity.value.tenant_domain
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
})

// Picking a server settles its cluster and how many tenants it should hold.
watch(server, (s) => {
  if (!s) return
  form.press_cluster = s.cluster || ''
  if (s.recommended_capacity) form.capacity_tenants = s.recommended_capacity
})

// Picking a bench group settles its version and its apps.
watch(group, async (g) => {
  form.press_version = g?.version || ''
  form.site_apps = ''
  appsError.value = ''
  if (!g) return

  appsLoading.value = true
  try {
    const result = await api.benchApps(g.name)
    if (result?.available) {
      form.site_apps = (result.apps || []).map((a) => a.app).join(',')
    } else {
      appsError.value = result?.error || 'Frappe Cloud did not answer'
    }
  } finally {
    appsLoading.value = false
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    await api.createShard({ ...form })
    open.value = false
    emit('created')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}
</script>

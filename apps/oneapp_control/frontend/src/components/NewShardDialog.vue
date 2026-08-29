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

      <FormControl
        v-model="form.press_server"
        type="select"
        label="Server"
        :options="serverOptions"
        description="Read live from Frappe Cloud, so the name always matches."
      />
      <FormControl
        v-model="form.press_release_group"
        type="select"
        label="Bench group"
        :options="groupOptions"
      />

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
        <FormControl v-model="form.press_version" label="Frappe version" placeholder="Nightly" />
        <FormControl
          v-model="form.environment"
          type="select"
          label="Environment"
          :options="['Production', 'Staging']"
          description="Staging shards may be patched and redeployed automatically."
        />
        <FormControl v-model="form.capacity_tenants" type="number" label="Soft cap (tenants)" />
        <FormControl v-model="form.standby_target" type="number" label="Standby sites" />
      </div>

      <FormControl
        v-model="form.site_apps"
        label="Apps to install"
        placeholder="frappe, erpnext, payments, oneapp"
        description="Comma separated, in install order."
      />

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
const error = ref('')
const capacity = ref({ servers: [], release_groups: [], regions: [], existing: [] })

const form = reactive({
  shard_name: '',
  press_server: '',
  press_release_group: '',
  region: '',
  domain: '',
  press_version: 'Nightly',
  environment: 'Production',
  capacity_tenants: 60,
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

const alreadyUsed = computed(() =>
  (capacity.value.existing || []).some(
    ([server, group]) => server === form.press_server && group === form.press_release_group,
  ),
)

const complete = computed(
  () =>
    form.shard_name &&
    form.press_server &&
    form.press_release_group &&
    form.region &&
    form.domain,
)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  error.value = ''
  try {
    capacity.value = (await api.pressCapacity()) || capacity.value
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
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

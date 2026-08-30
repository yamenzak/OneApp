<template>
  <SettingsHeader
    title="AI features"
    description="What the fleet's apps declare. Nobody maintains this list — sites report what their code registers, so a feature appears here the moment an app ships it."
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div v-if="loading && !features.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!features.length"
      class="!py-12"
      icon="lucide-sparkles"
      title="No features declared yet"
      description="Apps register them with @ai_feature. Sites report their registry on the next sync."
    />

    <div v-else class="-mx-4 overflow-x-auto px-4 pt-5 sm:mx-0 sm:px-0">
      <List :columns="columns" :row-height="56" class="min-w-[36rem] list-row-px-3" divider="full">
        <ListHeader>
          <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
        </ListHeader>
        <ListRows :items="features" row-key="name" v-slot="{ item: feature, value }">
          <ListRow :value="value" @click="edit(feature)">
            <ListCell v-if="shows('feature')">
              <div class="flex min-w-0 flex-col">
                <span class="truncate text-p-sm text-ink-gray-8">{{ feature.label }}</span>
                <span class="truncate text-p-xs text-ink-gray-5">{{ feature.name }}</span>
              </div>
            </ListCell>
            <ListCell v-if="shows('capability')">
              <span class="truncate text-p-sm text-ink-gray-6">{{ feature.capability }}</span>
            </ListCell>
            <ListCell v-if="shows('control')">
              <Badge
                v-if="!feature.tenant_can_disable"
                theme="blue"
                label="Always on"
                variant="subtle"
              />
              <span v-else class="text-p-xs text-ink-gray-5">Workspace chooses</span>
            </ListCell>
            <ListCell v-if="shows('status')">
              <Badge
                :theme="feature.status === 'Active' ? 'green' : 'amber'"
                :label="feature.status"
                variant="subtle"
              />
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </div>
  </SettingsBody>

  <Dialog v-model="showForm" :title="editing?.label || 'Feature'" size="lg">
    <div v-if="editing" class="flex flex-col gap-4">
      <p class="text-p-sm text-ink-gray-6">{{ editing.description }}</p>

      <!--
          Not editable, and the reason is worth saying out loud: whether a
          workflow can run without AI is a property of the code, declared by the
          app that has to keep working afterwards.
        -->
      <Alert
        v-if="!editing.tenant_can_disable"
        theme="blue"
        title="Workspaces cannot switch this off"
      >
        <template #description>
          The app declared AI as the process here rather than an assistant beside it, so this keeps
          running even for a workspace that turns AI off. Changing that means changing the app.
        </template>
      </Alert>

      <FormControl
        v-model="form.status"
        type="select"
        label="Status"
        :options="['Active', 'Suspended', 'Withdrawn']"
        description="Suspended stops every workspace calling it, without a deploy."
      />
      <FormControl
        v-model="form.default_model"
        type="select"
        label="Default model"
        :options="modelOptions"
        description="Used where a workspace has not chosen. Empty falls back to whatever is recommended for this capability."
      />
      <div class="grid grid-cols-2 gap-3">
        <FormControl v-model="form.max_input_tokens" type="number" label="Max input tokens" />
        <FormControl v-model="form.max_output_tokens" type="number" label="Max output tokens" />
        <FormControl v-model="form.max_images" type="number" label="Max images" />
        <FormControl v-model="form.max_credits" type="number" label="Max credits per call" />
      </div>
      <p class="text-p-xs text-ink-gray-5">
        These are the ceiling a call is held against before it runs, not a forecast of what it will
        cost. The charge is always what the model reported it used.
      </p>
    </div>
    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  SettingsHeader,
  SettingsBody,
  Button,
  Badge,
  Alert,
  Dialog,
  FormControl,
  List,
  ListHeader,
  ListHeaderCell,
  ListRows,
  ListRow,
  ListCell,
  LoadingIndicator,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { useListColumns } from '../../lib/list'
import { ai } from '../../lib/ai'
import { activeSettingsTab } from '../../lib/settings'

const { visible, columns, shows } = useListColumns([
  { key: 'feature', header: 'Feature', track: 'minmax(0,1fr)' },
  { key: 'capability', header: 'Capability', track: '11rem', mobile: false },
  { key: 'control', header: 'Control', track: '10rem', mobile: false },
  { key: 'status', header: 'Status', track: '8rem', mobile: '7rem' },
])

const features = ref([])
const models = ref([])
const loading = ref(false)
const saving = ref(false)
const showForm = ref(false)
const editing = ref(null)
const form = ref({})

// Only models that can do what the feature asked for. Offering the rest is
// offering a default that fails on first use.
const modelOptions = computed(() => [
  { label: 'Whatever is recommended', value: '' },
  ...models.value
    .filter((m) => m.capability === editing.value?.capability)
    .map((m) => ({
      label: `${m.display_name} (${m.provider})`,
      value: m.name,
    })),
])

const reload = async () => {
  loading.value = true
  try {
    const [list, catalogue] = await Promise.all([ai.features(), ai.models({ status: 'Available' })])
    features.value = list || []
    models.value = catalogue || []
  } finally {
    loading.value = false
  }
}

const edit = (feature) => {
  editing.value = feature
  form.value = {
    status: feature.status,
    default_model: feature.default_model || '',
    max_input_tokens: feature.max_input_tokens || 0,
    max_output_tokens: feature.max_output_tokens || 0,
    max_images: feature.max_images || 0,
    max_credits: feature.max_credits || 0,
  }
  showForm.value = true
}

const save = async () => {
  saving.value = true
  try {
    await ai.updateFeature(editing.value.name, {
      status: form.value.status,
      default_model: form.value.default_model || null,
      max_input_tokens: Number(form.value.max_input_tokens) || 0,
      max_output_tokens: Number(form.value.max_output_tokens) || 0,
      max_images: Number(form.value.max_images) || 0,
      max_credits: Number(form.value.max_credits) || 0,
    })
    showForm.value = false
    await reload()
  } finally {
    saving.value = false
  }
}

watch(
  activeSettingsTab,
  (tab) => {
    if (tab === 'ai-features' && !features.value.length) reload()
  },
  { immediate: true },
)
</script>

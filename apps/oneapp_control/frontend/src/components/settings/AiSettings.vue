<template>
  <SettingsHeader
    title="AI models"
    description="Fetched from Cloudflare and Google, priced from what they publish. Sold at a markup you set; never at a price we guessed."
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button icon="lucide-refresh-cw" label="Refresh catalogue" :loading="syncing" @click="sync" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <div v-if="loading && !models.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else class="flex flex-col gap-4 pt-5">
      <!-- Said plainly rather than left as an empty table: a catalogue with no
           models looks like a broken page, and the reason is almost always a
           credential nobody set. -->
      <Alert
        v-if="!settings.has_cloudflare || !settings.has_google"
        theme="amber"
        title="The catalogue cannot refresh itself yet"
      >
        <template #description>
          <span v-if="!settings.has_cloudflare">
            Workers AI needs a Cloudflare account ID and an API token with
            <strong>Workers AI: Read</strong> and <strong>AI Gateway: Read</strong>.
          </span>
          <span v-if="!settings.has_google"> Gemini needs a Google AI Studio key. </span>
          Both are on the Cloudflare and Frappe Cloud tabs.
        </template>
      </Alert>

      <div class="flex flex-wrap items-end gap-3">
        <FormControl
          v-model="markup"
          type="number"
          size="sm"
          label="Markup"
          class="w-32"
          description="Applied to measured cost."
        />
        <Button label="Save markup" :loading="savingMarkup" @click="saveMarkup" />
        <span class="pb-2 text-p-xs text-ink-gray-5">
          A model can override this on its own row.
        </span>
      </div>

      <div class="flex flex-wrap gap-2">
        <TabButtons v-model="capability" :options="capabilityTabs" />
      </div>

      <p v-if="settings.note" class="text-p-xs text-ink-gray-5">
        Last refreshed {{ settings.synced_on || 'never' }} — {{ settings.note }}
      </p>

      <EmptyState
        v-if="!filtered.length"
        class="!py-12"
        icon="lucide-sparkles"
        title="No models"
        :description="
          models.length
            ? 'Nothing in the catalogue does this yet.'
            : 'Refresh the catalogue once the credentials above are set.'
        "
      />

      <!-- Wide content owns its own horizontal scroller: SettingsBody's
           ScrollArea is vertical-only and would clip the rest. -->
      <div v-else class="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        <List
          :columns="columns"
          :row-height="56"
          class="min-w-[40rem] list-row-px-3"
          divider="full"
        >
          <ListHeader>
            <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
          </ListHeader>
          <ListRows :items="filtered" row-key="name" v-slot="{ item: model, value }">
            <ListRow :value="value" @click="edit(model)">
              <ListCell v-if="shows('model')">
                <div class="flex min-w-0 flex-col">
                  <span class="truncate text-p-sm text-ink-gray-8">{{ model.display_name }}</span>
                  <span class="truncate text-p-xs text-ink-gray-5">{{ model.model_id }}</span>
                </div>
              </ListCell>
              <ListCell v-if="shows('provider')">
                <span class="truncate text-p-sm text-ink-gray-6">{{ model.provider }}</span>
              </ListCell>
              <ListCell v-if="shows('rate')">
                <div class="flex min-w-0 flex-col">
                  <span
                    v-for="line in rateLines(model).slice(0, 2)"
                    :key="line"
                    class="truncate text-p-xs text-ink-gray-6"
                    >{{ line }}</span
                  >
                  <span v-if="!rateLines(model).length" class="text-p-xs text-ink-gray-4">
                    no rate
                  </span>
                </div>
              </ListCell>
              <ListCell v-if="shows('status')">
                <div class="flex items-center gap-1">
                  <Badge
                    :theme="STATUS_THEME[model.status] || 'gray'"
                    :label="model.status"
                    variant="subtle"
                  />
                  <Badge
                    v-if="model.is_recommended"
                    theme="blue"
                    label="Default"
                    variant="subtle"
                  />
                </div>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </div>
    </div>
  </SettingsBody>

  <Dialog v-model="showForm" :title="editing?.display_name || 'Model'" size="lg">
    <div v-if="editing" class="flex flex-col gap-4">
      <!-- The rates are shown and not editable on purpose: they come from the
             provider and the next refresh overwrites them, so a field here
             would be a control that silently stops working. -->
      <div class="rounded-4 bg-surface-gray-1 p-3">
        <p class="mb-1 text-p-xs font-medium text-ink-gray-7">
          Published rates — from {{ editing.source }}
        </p>
        <p v-for="line in rateLines(editing)" :key="line" class="text-p-xs text-ink-gray-6">
          {{ line }}
        </p>
        <p v-if="!rateLines(editing).length" class="text-p-xs text-ink-gray-5">
          None could be read, which is why this model cannot be sold.
        </p>
      </div>

      <Alert v-if="editing.sync_note" theme="amber" title="From the last refresh">
        <template #description>{{ editing.sync_note }}</template>
      </Alert>

      <FormControl
        v-model="form.status"
        type="select"
        label="Status"
        :options="['Available', 'Preview', 'Needs Review', 'Deprecated', 'Retired']"
        description="Only Available and Preview can be chosen by a workspace or called."
      />
      <FormControl
        v-model="form.markup_override"
        type="number"
        label="Markup override"
        :description="`0 uses the global ${settings.markup}.`"
      />
      <FormControl
        v-model="form.is_recommended"
        type="checkbox"
        label="Recommend for this capability"
        description="Chosen for features that have not pinned a model, and pre-selected in a workspace's picker."
      />
      <div class="grid grid-cols-2 gap-3 text-p-xs text-ink-gray-6">
        <span>Takes: {{ editing.input_modalities || '—' }}</span>
        <span>Returns: {{ editing.output_modalities || '—' }}</span>
        <span>Context: {{ editing.context_window || '—' }}</span>
        <span>Max output: {{ editing.max_output_tokens || '—' }}</span>
      </div>
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
  TabButtons,
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
import { ai, rateLines, STATUS_THEME } from '../../lib/ai'
import { activeSettingsTab } from '../../lib/settings'

// Destructured, not held as an object: reaching a ref through a property does
// not unwrap it in a template, and List would be handed a ComputedRef.
const { visible, columns, shows } = useListColumns([
  { key: 'model', header: 'Model', track: 'minmax(0,1fr)' },
  { key: 'provider', header: 'Provider', track: '10rem', mobile: false },
  { key: 'rate', header: 'Rate', track: 'minmax(0,14rem)', mobile: false },
  { key: 'status', header: 'Status', track: '11rem', mobile: '8rem' },
])

const models = ref([])
const settings = ref({})
const loading = ref(false)
const syncing = ref(false)
const saving = ref(false)
const savingMarkup = ref(false)
const markup = ref(1.5)
const capability = ref('All')
const showForm = ref(false)
const editing = ref(null)
const form = ref({})

const capabilityTabs = computed(() => {
  const found = [...new Set(models.value.map((m) => m.capability))].sort()
  return ['All', ...found].map((label) => ({ label, value: label }))
})

const filtered = computed(() =>
  capability.value === 'All'
    ? models.value
    : models.value.filter((m) => m.capability === capability.value),
)

const reload = async () => {
  loading.value = true
  try {
    const [list, conf] = await Promise.all([ai.models(), ai.settings()])
    models.value = list || []
    settings.value = conf || {}
    markup.value = conf?.markup || 1.5
  } finally {
    loading.value = false
  }
}

const sync = async () => {
  syncing.value = true
  try {
    await ai.sync()
    await reload()
  } finally {
    syncing.value = false
  }
}

const saveMarkup = async () => {
  savingMarkup.value = true
  try {
    await ai.setMarkup(Number(markup.value))
    await reload()
  } finally {
    savingMarkup.value = false
  }
}

const edit = (model) => {
  editing.value = model
  form.value = {
    status: model.status,
    markup_override: model.markup_override || 0,
    is_recommended: !!model.is_recommended,
  }
  showForm.value = true
}

const save = async () => {
  saving.value = true
  try {
    await ai.updateModel(editing.value.name, {
      status: form.value.status,
      markup_override: Number(form.value.markup_override) || 0,
      is_recommended: form.value.is_recommended ? 1 : 0,
    })
    showForm.value = false
    await reload()
  } finally {
    saving.value = false
  }
}

// Fetched when the tab is first looked at: this reads every model and its rate
// rows, and most sessions never open it.
watch(
  activeSettingsTab,
  (tab) => {
    if (tab === 'ai' && !models.value.length) reload()
  },
  { immediate: true },
)
</script>

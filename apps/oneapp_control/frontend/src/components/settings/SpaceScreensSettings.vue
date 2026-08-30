<template>
  <SettingsHeader
    title="Space screens"
    description="What an app puts in front of a customer. A screen names a doctype and the fields worth showing; OneSpace renders the list and the record from the tenant site's own metadata, so most apps need no frontend code at all."
    :class="PANEL_HEADER"
  >
    <template v-if="app" #actions>
      <Button icon-left="lucide-plus" label="Add screen" @click="add" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <div v-if="loading && !apps.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!apps.length"
      class="!py-12"
      icon="lucide-layout-grid"
      title="No apps registered"
      description="Register one on the Apps tab first; screens belong to an app."
    />

    <div v-else class="flex flex-col gap-4 pt-6">
      <FormControl
        v-model="app"
        type="select"
        label="App"
        :options="appOptions"
        description="Screens are per app, and their order here is the order of the app's navigation."
      />

      <EmptyState
        v-if="app && !screens.length"
        class="!py-8"
        icon="lucide-hammer"
        title="No screens yet"
        description="An app with none is an entitlement with no interface — a real thing to be, since it still grants its roles and doctypes."
      />

      <div
        v-for="(screen, index) in screens"
        :key="index"
        class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 p-4"
      >
        <div class="flex items-center justify-between gap-3">
          <span class="text-base-medium text-ink-gray-8">
            {{ screen.label || 'Untitled screen' }}
          </span>
          <Button
            icon="lucide-trash-2"
            variant="ghost"
            label="Remove screen"
            @click="screens.splice(index, 1)"
          />
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <FormControl v-model="screen.label" label="Label" placeholder="Invoices" />
          <FormControl
            v-model="screen.screen"
            label="Slug"
            placeholder="invoices"
            description="In the URL. Stable — a bookmark points at it."
          />
          <FormControl v-model="screen.icon" type="select" label="Icon" :options="ICONS" />
          <FormControl
            v-model="screen.document_type"
            label="Doctype"
            placeholder="Sales Invoice"
            description="Must also be in the app's manifest below."
          />
          <FormControl
            v-model="screen.fields"
            label="Columns"
            placeholder="customer,status,grand_total"
            description="Comma-separated. Labels and types come from the tenant site. Empty uses the doctype's own list fields."
          />
          <FormControl v-model="screen.order_by" label="Order by" placeholder="modified desc" />
          <FormControl
            v-model="screen.filters"
            type="textarea"
            label="Always filter by"
            :rows="2"
            :placeholder="FILTER_EXAMPLE"
          />
          <FormControl
            v-model="screen.component"
            label="Custom component"
            placeholder="crm/pipeline"
            description="Escape hatch for a screen a list cannot be. Set it and the doctype above is ignored."
          />
        </div>
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <div v-if="app" :class="PANEL_FOOTER">
    <Button variant="solid" label="Save" :loading="saving" @click="save" />
    <span class="text-p-sm text-ink-gray-5"> Reaches a workspace on its next sync. </span>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  SettingsHeader,
  SettingsBody,
  Button,
  FormControl,
  ErrorMessage,
  LoadingIndicator,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { SPACE_ICONS } from '../../lib/icons'
import { api, useDocList } from '../../lib/api'
import { activeSettingsTab } from '../../lib/settings'

const ICONS = SPACE_ICONS

// In a constant because the example is JSON, and JSON in a template attribute
// fights the linter's quoting rule.
const FILTER_EXAMPLE = '{"status": "Open"}'

const app = ref('')
const screens = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const appList = useDocList('OneSpace Space', {
  fields: ['name', 'space_label'],
  orderBy: 'sort_order asc',
  limit: 200,
})

const apps = computed(() => appList.data || [])
const appOptions = computed(() =>
  apps.value.map((a) => ({ label: a.space_label || a.name, value: a.name })),
)

const add = () => {
  screens.value.push({
    screen: '',
    label: '',
    icon: 'lucide-layout-grid',
    document_type: '',
    fields: '',
    component: '',
    filters: '',
    order_by: 'modified desc',
  })
}

const loadViews = async () => {
  if (!app.value) {
    screens.value = []
    return
  }
  loading.value = true
  try {
    screens.value = (await api.appViews(app.value)) || []
  } finally {
    loading.value = false
  }
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await api.setAppViews(app.value, screens.value)
    await loadViews()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

watch(app, loadViews)

// The first app, so the panel opens on something rather than on a picker.
watch(apps, (found) => {
  if (!app.value && found.length) app.value = found[0].name
})

watch(
  activeSettingsTab,
  (tab) => {
    if (tab === 'app-screens' && app.value && !screens.value.length) loadViews()
  },
  { immediate: true },
)
</script>

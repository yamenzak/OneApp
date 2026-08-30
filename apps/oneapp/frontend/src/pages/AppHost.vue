<template>
  <PageHeader>
    <Breadcrumbs :items="crumbs" />
    <template v-if="spec?.can_create" #right>
      <Button variant="solid" icon-left="lucide-plus" label="New" @click="create" />
    </template>
  </PageHeader>

  <div class="p-5">
    <div v-if="loading" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!app"
      icon="lucide-circle-help"
      title="App not available"
      description="This app is not enabled for your workspace, or you do not have access to it."
    />

    <!-- A screen the app wrote itself. Nothing else on the view applies. -->
    <component :is="custom" v-else-if="custom" :app-code="appCode" :view="spec.view" />

    <!--
      An entitlement with no interface is a real thing to be: it still grants
      its roles and doctypes, and something else may be using them.
    -->
    <EmptyState
      v-else-if="!spec?.views?.length"
      icon="lucide-hammer"
      title="Nothing to show yet"
      :description="`${app.app_label} is enabled for this workspace but has no screens.`"
    />

    <Alert v-else-if="spec.error" theme="amber" :title="spec.view_label">
      <template #description>{{ spec.error }}</template>
    </Alert>

    <template v-else>
      <div v-if="rowsLoading && !rows.length" class="grid place-items-center py-20">
        <LoadingIndicator class="size-5 text-ink-gray-5" />
      </div>

      <EmptyState
        v-else-if="!rows.length"
        icon="lucide-inbox"
        :title="`No ${spec.view_label.toLowerCase()} yet`"
        :description="
          spec.can_create
            ? 'Nothing here so far. New starts the first one.'
            : 'Nothing here so far.'
        "
      />

      <!-- Wide content owns its own horizontal scroller rather than stretching
           the page: a doctype with six columns does not fit a phone. -->
      <div v-else class="-mx-5 overflow-x-auto px-5 sm:mx-0 sm:px-0">
        <List
          :columns="tracks"
          :row-height="48"
          class="list-row-px-3"
          :class="wide && 'min-w-[36rem]'"
          divider="full"
        >
          <ListHeader>
            <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
          </ListHeader>
          <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
            <ListRow :value="value" @click="open(row)">
              <ListCell v-for="c in visible" :key="c.key">
                <span class="truncate text-p-sm text-ink-gray-8">
                  {{ display(row, c.column) }}
                </span>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </div>
    </template>
  </div>

  <Dialog v-model="showRecord" :title="recordTitle" size="xl">
    <div v-if="editing" class="flex flex-col gap-4">
      <template v-for="field in formFields" :key="field.fieldname">
        <Switch
          v-if="field.fieldtype === 'Check'"
          v-model="form[field.fieldname]"
          :label="field.label"
          :disabled="!writable(field)"
        />
        <FormControl
          v-else
          v-model="form[field.fieldname]"
          :type="inputType(field)"
          :label="field.label"
          :options="field.fieldtype === 'Select' ? selectOptions(field) : undefined"
          :required="!!field.reqd"
          :disabled="!writable(field)"
        />
      </template>
      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template v-if="spec?.can_write" #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  PageHeader,
  Breadcrumbs,
  Button,
  Dialog,
  FormControl,
  Switch,
  Alert,
  ErrorMessage,
  LoadingIndicator,
  List,
  ListHeader,
  ListHeaderCell,
  ListRows,
  ListRow,
  ListCell,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { useListColumns } from '../lib/list'
import { appComponent } from '../apps'

const props = defineProps({ appCode: { type: String, required: true } })
const route = useRoute()

const spec = ref(null)
const loading = ref(false)
const showRecord = ref(false)
const editing = ref(null)
const saving = ref(false)
const error = ref('')
const form = reactive({})

const app = computed(() => (session.apps || []).find((a) => a.app_code === props.appCode))

const custom = computed(() => {
  const name = spec.value?.component
  return name ? appComponent(name) : null
})

// Only the columns the resolved view actually named. Declared through
// useListColumns so a six-column doctype drops to two on a phone rather than
// truncating the one column a row exists to name.
const columnSpec = computed(() =>
  (spec.value?.columns || []).map((column, index) => ({
    key: column.fieldname,
    header: column.label,
    track: index === 0 ? 'minmax(0,1fr)' : '10rem',
    // The identity column and one more. Everything else is in the record.
    mobile: index < 2,
    column,
  })),
)

const { visible, columns: tracks } = useListColumns(columnSpec)

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned, which
// is how the frappe-ui prop guard read `visible.length` as a prop name.
const wide = computed(() => visible.value.length > 3)

// Not useDocList: which doctype this screen lists is not known until the view
// has resolved, and a list resource built at setup would have been handed a
// null doctype, plus a ref where its socket subscription wanted a name. The
// rows come from the same endpoint that resolved the view instead — one round
// trip, and the same bounds on both.
const rows = ref([])
const hasMore = ref(false)
const rowsLoading = ref(false)

const crumbs = computed(() => {
  const trail = [{ label: 'Apps', route: { name: 'Launcher' } }]
  if (app.value) trail.push({ label: app.value.app_label })
  if (spec.value?.view_label && spec.value.views?.length > 1) {
    trail.push({ label: spec.value.view_label })
  }
  return trail
})

const formFields = computed(() => spec.value?.columns || [])

const recordTitle = computed(() => {
  if (!editing.value) return spec.value?.view_label || ''
  if (editing.value.__new) return `New ${spec.value?.view_label || 'record'}`
  return editing.value[spec.value?.title_field] || editing.value.name
})

const writable = (field) => !!spec.value?.can_write && !!field.editable
const selectOptions = (field) => (field.options || '').split('\n').filter(Boolean)

const INPUT_TYPES = {
  Int: 'number',
  Float: 'number',
  Currency: 'number',
  Percent: 'number',
  Date: 'date',
  Datetime: 'datetime-local',
  Time: 'time',
  Select: 'select',
  'Small Text': 'textarea',
  Text: 'textarea',
  'Long Text': 'textarea',
  'Text Editor': 'textarea',
}
const inputType = (field) => INPUT_TYPES[field.fieldtype] || 'text'

const display = (row, column) => {
  const value = row[column.fieldname]
  if (value === null || value === undefined || value === '') return '—'
  if (column.fieldtype === 'Check') return value ? 'Yes' : 'No'
  return value
}

const open = (row) => {
  editing.value = row
  error.value = ''
  Object.keys(form).forEach((key) => delete form[key])
  for (const field of formFields.value) form[field.fieldname] = row[field.fieldname]
  showRecord.value = true
}

const create = () => {
  open({ __new: true })
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await workspace.saveAppRecord(
      props.appCode,
      spec.value.view,
      { ...form },
      editing.value.__new ? null : editing.value.name,
    )
    showRecord.value = false
    await loadRows()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

const loadRows = async () => {
  if (!spec.value?.doctype) {
    rows.value = []
    return
  }
  rowsLoading.value = true
  try {
    const page = await workspace.appRows(props.appCode, spec.value.view)
    rows.value = page?.rows || []
    hasMore.value = !!page?.has_more
  } finally {
    rowsLoading.value = false
  }
}

const load = async () => {
  if (!app.value) return
  loading.value = true
  try {
    spec.value = await workspace.appView(props.appCode, route.query.view || '')
    await loadRows()
  } finally {
    loading.value = false
  }
}

// Re-resolved on every view change: the columns, the filters and what this user
// may do are all per view, not per app.
watch([() => props.appCode, () => route.query.view, () => session.loaded], load, {
  immediate: true,
})
</script>

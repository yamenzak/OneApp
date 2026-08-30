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
      <ViewControls
        class="mb-4"
        :spec="spec"
        :app-code="appCode"
        :view="spec.view"
        @changed="onViewChanged"
      />

      <!--
        Skeleton rows rather than a spinner: the shape of what is coming is
        already known, and a list that appears in place reads as loading where a
        spinner reads as blocked.
      -->
      <div v-if="rowsLoading && !rows.length" class="flex flex-col gap-2 pt-2">
        <Skeleton v-for="n in 6" :key="n" class="h-11 w-full" />
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
            <ListHeaderCell v-for="c in visible" :key="c.key">
              <span class="flex min-w-0 items-center gap-1.5">
                <!-- The field's own icon, so a header reads at a glance. -->
                <Icon :name="c.column.icon" class="size-3.5 shrink-0 text-ink-gray-4" />
                <span class="truncate">{{ c.header }}</span>
              </span>
            </ListHeaderCell>
          </ListHeader>
          <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
            <ListRow :value="value" @click="open(row)">
              <ListCell v-for="c in visible" :key="c.key">
                <div class="flex min-w-0 items-center gap-2">
                  <!-- The record's picture, where the doctype names one. -->
                  <Avatar
                    v-if="c.first && spec.image_field && row[spec.image_field]"
                    :image="row[spec.image_field]"
                    :label="String(row[c.column.fieldname] || row.name)"
                    shape="square"
                    size="sm"
                  />
                  <FieldCell
                    :column="c.column"
                    :value="row[c.column.fieldname]"
                    :states="spec.states"
                  />
                </div>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>

        <p v-if="hasMore" class="px-1 pt-3 text-p-xs text-ink-gray-5">
          Showing the first {{ rows.length }}. Narrow the list to find something older.
        </p>
      </div>
    </template>
  </div>

  <RecordDialog
    v-if="spec?.doctype"
    v-model="showRecord"
    :record="editing || {}"
    :spec="spec"
    :app-code="appCode"
    :view="spec.view"
    @saved="loadRows"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  PageHeader,
  Breadcrumbs,
  Button,
  Alert,
  Avatar,
  Icon,
  Skeleton,
  LoadingIndicator,
  List,
  ListHeader,
  ListHeaderCell,
  ListRows,
  ListRow,
  ListCell,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FieldCell from '../components/app/FieldCell.vue'
import RecordDialog from '../components/app/RecordDialog.vue'
import ViewControls from '../components/app/ViewControls.vue'
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
const rows = ref([])
// The columns the rows were actually fetched with, which is not always the
// screen's: an unsaved change to the column list narrows the fetch, and a
// header list that does not follow leaves a column standing over empty cells.
const columns = ref([])
const hasMore = ref(false)
const rowsLoading = ref(false)
const pending = ref(null)

const app = computed(() => (session.apps || []).find((a) => a.app_code === props.appCode))

const custom = computed(() => {
  const name = spec.value?.component
  return name ? appComponent(name) : null
})

// Only the columns the resolved view actually named. Declared through
// useListColumns so a six-column doctype drops to two on a phone rather than
// truncating the one column a row exists to name.
const columnSpec = computed(() =>
  (columns.value || []).map((column, index) => ({
    key: column.fieldname,
    header: column.label,
    // The identity column gets the room. With five 10rem columns beside it a
    // bare `1fr` came out the narrowest of the six, so the one field a row
    // exists to name was the one truncated.
    track: index === 0 ? 'minmax(12rem,2fr)' : '9rem',
    // The identity column and one more. Everything else is in the record.
    mobile: index < 2,
    first: index === 0,
    column,
  })),
)

const { visible, columns: tracks } = useListColumns(columnSpec)

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned, which
// is how the frappe-ui prop guard read `visible.length` as a prop name.
const wide = computed(() => visible.value.length > 3)

const crumbs = computed(() => {
  const trail = [{ label: 'Apps', route: { name: 'Launcher' } }]
  if (app.value) trail.push({ label: app.value.app_label })
  if (spec.value?.view_label && spec.value.views?.length > 1) {
    trail.push({ label: spec.value.view_label })
  }
  return trail
})

const open = (row) => {
  editing.value = row
  showRecord.value = true
}

const create = () => open({ __new: true })

const loadRows = async () => {
  if (!spec.value?.doctype) {
    rows.value = []
    columns.value = spec.value?.columns || []
    return
  }
  rowsLoading.value = true
  try {
    const page = await workspace.appRows(props.appCode, spec.value.view, pending.value)
    rows.value = page?.rows || []
    columns.value = page?.columns || spec.value.columns || []
    hasMore.value = !!page?.has_more
  } finally {
    rowsLoading.value = false
  }
}

// A change that has not been saved still has to show: the list answers the
// question the controls are asking, saved or not.
const onViewChanged = async (payload, options = {}) => {
  pending.value = payload
  if (options.reload) {
    pending.value = null
    await load()
    return
  }
  await loadRows()
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
watch(
  [() => props.appCode, () => route.query.view, () => session.loaded],
  () => {
    pending.value = null
    load()
  },
  { immediate: true },
)
</script>

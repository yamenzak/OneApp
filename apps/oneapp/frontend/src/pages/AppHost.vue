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
      <!--
        The quick boxes get a row of their own — Frappe's standard filter area.
        Most questions are "the open ones" rather than a filter builder, and a
        box you can type into beats a panel you have to open.
      -->
      <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start">
        <QuickFilters class="min-w-0 flex-1" :spec="spec" @changed="onQuickFilters" />
        <!-- Its own line on a phone. Beside a wrapping row of boxes the actions
             end up sitting on top of one. -->
        <div class="flex shrink-0 items-center gap-1">
          <FilterPanel
            :filters="panelFilters"
            :columns="spec.all_columns || []"
            :app-code="appCode"
            :view="spec.view"
            @changed="onPanelFilters"
          />
          <!--
            Frappe puts these in the list header and that is where they belong
            visually — but the list header does not exist when the list is
            empty, and "only my favourites" with nothing liked is exactly when
            you need the button that turns it off again.
          -->
          <Button
            icon="lucide-heart"
            :variant="favourites ? 'subtle' : 'ghost'"
            :theme="favourites ? 'red' : 'gray'"
            label="Only my favourites"
            @click="toggleFavourites"
          />
          <Button
            icon="lucide-settings-2"
            variant="ghost"
            label="Choose columns"
            @click="showColumns = true"
          />
          <Button
            v-if="dirty"
            icon-left="lucide-bookmark"
            label="Save this view"
            :loading="saving"
            @click="saveView"
          />
          <Button
            v-if="spec.saved"
            icon="lucide-rotate-ccw"
            label="Back to the default view"
            variant="ghost"
            :loading="resetting"
            @click="resetView"
          />
        </div>
      </div>

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
        :title="favourites ? 'Nothing here yet' : `No ${spec.view_label.toLowerCase()} yet`"
        :description="emptyBecause"
      />

      <!-- Wide content owns its own horizontal scroller rather than stretching
           the page: a doctype with six columns does not fit a phone. -->
      <div v-else class="-mx-5 overflow-x-auto px-5 sm:mx-0 sm:px-0">
        <List
          :columns="tracks"
          :row-height="52"
          class="list-row-px-3"
          :class="wide && 'min-w-[42rem]'"
          divider="full"
        >
          <ListHeader>
            <!--
              Sorting lives on the headers, which is where everybody reaches
              first and the only place a direction can sit beside the thing it
              applies to. frappe-ui ships the cell for it — a real button, the
              aria-sort, the arrow that appears on hover — so this wires state
              to it rather than rebuilding it.
            -->
            <ListHeaderCellSort
              v-for="c in sortableColumns"
              :key="c.key"
              :direction="directionFor(c)"
              @click="sortBy(c.column.fieldname)"
            >
              <template #prefix>
                <Icon :name="c.column.icon" class="size-3.5 text-ink-gray-4" />
              </template>
              {{ c.header }}
            </ListHeaderCellSort>

            <!-- How many, over the column that carries each row's age. -->
            <ListHeaderCell v-if="metaColumn" :class="PINNED">
              <span class="ml-auto whitespace-nowrap text-p-xs text-ink-gray-5">
                {{ counted }}
              </span>
            </ListHeaderCell>
          </ListHeader>

          <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
            <ListRow :value="value" @click="open(row)">
              <ListCell v-for="c in visible" :key="c.key" :class="c.pinned && PINNED">
                <TitleCell
                  v-if="c.cell === 'title'"
                  :row="row"
                  :title-field="spec.title_field"
                  :image-field="spec.image_field"
                />
                <RowMeta v-else-if="c.cell === 'meta'" :meta="row._meta || {}" @like="like(row)" />
                <FieldCell
                  v-else
                  :column="c.column"
                  :value="row[c.column.fieldname]"
                  :states="spec.states"
                />
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

  <ColumnPicker
    v-if="spec?.doctype"
    v-model="showColumns"
    :chosen="chosenColumns"
    :offered="spec.all_columns || []"
    @update:chosen="onColumns"
  />

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
  Skeleton,
  LoadingIndicator,
  List,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRows,
  ListRow,
  ListCell,
  Icon,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FieldCell from '../components/app/FieldCell.vue'
import TitleCell from '../components/app/TitleCell.vue'
import RowMeta from '../components/app/RowMeta.vue'
import RecordDialog from '../components/app/RecordDialog.vue'
import FilterPanel from '../components/app/FilterPanel.vue'
import QuickFilters from '../components/app/QuickFilters.vue'
import ColumnPicker from '../components/app/ColumnPicker.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { useListColumns } from '../lib/list'
import { appComponent } from '../apps'

const props = defineProps({ appCode: { type: String, required: true } })
const route = useRoute()

const spec = ref(null)
const loading = ref(false)
const showRecord = ref(false)
const showColumns = ref(false)
const editing = ref(null)
const rows = ref([])
const columns = ref([])
const hasMore = ref(false)
const rowsLoading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const dirty = ref(false)

// The two filter surfaces are separate lists that are asked together, which is
// what Frappe does: the boxes above answer the common question and the panel
// answers the rest, and neither clears the other.
const quickFilters = ref([])
const panelFilters = ref([])
const order = ref('')
const chosenColumns = ref([])
const favourites = ref(false)

const app = computed(() => (session.apps || []).find((a) => a.app_code === props.appCode))

const custom = computed(() => {
  const name = spec.value?.component
  return name ? appComponent(name) : null
})

// The title column stands in for the title field wherever it would have been,
// and leads the list when the field is not chosen at all: a row needs a name
// before it needs anything else. The meta column closes every list.
const columnSpec = computed(() => {
  const titleField = spec.value?.title_field
  const rest = (columns.value || []).filter((c) => c.fieldname !== titleField)

  const titleColumn = (spec.value?.all_columns || []).find((c) => c.fieldname === titleField)

  const title = {
    key: '__title',
    header: titleColumn?.label || 'Name',
    track: 'minmax(12rem,2fr)',
    mobile: true,
    cell: 'title',
    sortable: !!titleField,
    column: {
      fieldname: titleField || 'name',
      label: titleColumn?.label || 'Name',
      // The field's own icon, not a stand-in: this column *is* the title field,
      // and giving it a different icon than the picker shows for the same field
      // is two names for one thing.
      icon: titleColumn?.icon || 'lucide-type',
    },
  }

  const middle = rest.map((column) => ({
    key: column.fieldname,
    header: column.label,
    track: '9rem',
    // A phone shows the name and one more. Everything else is in the record.
    mobile: false,
    cell: column.cell,
    sortable: true,
    column,
  }))
  if (middle.length) middle[0].mobile = true

  return [
    title,
    ...middle,
    {
      key: '__meta',
      header: '',
      track: '10rem',
      mobile: true,
      cell: 'meta',
      sortable: false,
      pinned: true,
      column: { fieldname: 'modified', label: 'Last Updated', icon: 'lucide-clock' },
    },
  ]
})

const { visible, columns: tracks } = useListColumns(columnSpec)

// A list wide enough to scroll is exactly the list whose column picker you
// need, so the meta column is pinned to the right edge rather than scrolled off
// it. Opaque, or the columns it covers read through it.
// A list wide enough to scroll is exactly the list whose count you want to
// read, so the column carrying each row's age is pinned to the right edge.
// Opaque, or the columns sliding under it read through it.
//
// A constant rather than a literal in the template: a string inside a `:class`
// expression is read as a class list by the token audit, which then reports
// `meta` as a retired token.
const PINNED = 'sticky right-0 z-10 bg-surface-base'

const sortableColumns = computed(() => visible.value.filter((c) => c.cell !== 'meta'))
const metaColumn = computed(() => visible.value.some((c) => c.cell === 'meta'))

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned, which
// is how the frappe-ui prop guard read `visible.length` as a prop name.
const wide = computed(() => visible.value.length > 3)

const counted = computed(() =>
  hasMore.value ? `${rows.value.length}+` : String(rows.value.length),
)

const emptyBecause = computed(() => {
  if (favourites.value) return 'Nothing you have liked is on this screen.'
  if (quickFilters.value.length || panelFilters.value.length) {
    return 'Nothing matches the filters. Clear one to widen the list.'
  }
  return spec.value?.can_create
    ? 'Nothing here so far. New starts the first one.'
    : 'Nothing here so far.'
})

const crumbs = computed(() => {
  const trail = [{ label: 'Apps', route: { name: 'Launcher' } }]
  if (app.value) trail.push({ label: app.value.app_label })
  if (spec.value?.view_label && spec.value.views?.length > 1) {
    trail.push({ label: spec.value.view_label })
  }
  return trail
})

// --- sorting, from the headers ----------------------------------------------

const sortField = computed(() => (order.value || spec.value?.order_by || '').split(' ')[0])
const ascending = computed(
  () => (order.value || spec.value?.order_by || '').split(' ')[1] === 'asc',
)

const directionFor = (c) => {
  if (c.column.fieldname !== sortField.value) return undefined
  return ascending.value ? 'asc' : 'desc'
}

// Clicking the column already sorted flips it; clicking another starts on
// descending, which is what "show me the newest" means for most columns.
const sortBy = (fieldname) => {
  const flip = fieldname === sortField.value && !ascending.value
  order.value = `${fieldname} ${flip ? 'asc' : 'desc'}`
  changed()
}

// --- what the list is being asked -------------------------------------------

const payload = () => ({
  filters: [...quickFilters.value, ...panelFilters.value],
  order_by: order.value,
  columns: chosenColumns.value,
  favourites: favourites.value,
})

const changed = async () => {
  dirty.value = true
  await loadRows()
}

const onQuickFilters = (filters) => {
  quickFilters.value = filters
  changed()
}

const onPanelFilters = (filters) => {
  panelFilters.value = filters
  changed()
}

const onColumns = (chosen) => {
  chosenColumns.value = chosen
  changed()
}

const toggleFavourites = () => {
  favourites.value = !favourites.value
  changed()
}

// --- records ----------------------------------------------------------------

const open = (row) => {
  editing.value = row
  showRecord.value = true
}

const create = () => open({ __new: true })

const like = async (row) => {
  const result = await workspace.toggleLike(props.appCode, spec.value.view, row.name)
  // Patched in place rather than reloaded: a like is not a reason to lose the
  // reader's scroll position.
  row._meta = { ...row._meta, liked: !!result?.liked, likes: (result?.likes || []).length }
}

const loadRows = async () => {
  if (!spec.value?.doctype) {
    rows.value = []
    columns.value = spec.value?.columns || []
    return
  }
  rowsLoading.value = true
  try {
    const page = await workspace.appRows(props.appCode, spec.value.view, payload())
    rows.value = page?.rows || []
    // The columns the rows were actually fetched with, which is not always the
    // screen's: an unsaved change to the column list narrows the fetch, and a
    // header list that does not follow leaves a column standing over empty
    // cells.
    columns.value = page?.columns || spec.value.columns || []
    hasMore.value = !!page?.has_more
  } finally {
    rowsLoading.value = false
  }
}

const saveView = async () => {
  saving.value = true
  try {
    await workspace.saveView(props.appCode, spec.value.view, payload())
    dirty.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const resetView = async () => {
  resetting.value = true
  try {
    await workspace.resetView(props.appCode, spec.value.view)
    dirty.value = false
    await load()
  } finally {
    resetting.value = false
  }
}

const load = async () => {
  if (!app.value) return
  loading.value = true
  try {
    spec.value = await workspace.appView(props.appCode, route.query.view || '')
    // Seeded from what the screen resolved to, which already includes this
    // person's saved view.
    quickFilters.value = []
    panelFilters.value = (spec.value?.saved?.filters || []).map((filter) => [...filter])
    order.value = spec.value?.order_by || ''
    chosenColumns.value = (spec.value?.columns || []).map((c) => c.fieldname)
    favourites.value = !!spec.value?.saved?.favourites
    dirty.value = false
    await loadRows()
  } finally {
    loading.value = false
  }
}

// Re-resolved on every view change: the columns, the filters and what this user
// may do are all per view, not per app.
watch([() => props.appCode, () => route.query.view, () => session.loaded], () => load(), {
  immediate: true,
})
</script>

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
            The column picker and the favourites filter live in the activity
            column's header, where the heart lines up with the one on every row
            — but that column is data, and Frappe hides the activity area on a
            phone. So when it is not showing, these come here instead. Never
            both, never neither.
          -->
          <template v-if="!metaColumn">
            <Button
              icon="lucide-settings-2"
              variant="ghost"
              label="Choose columns"
              @click="showColumns = true"
            />
            <Button
              icon="lucide-heart"
              :variant="favourites ? 'subtle' : 'ghost'"
              :theme="favourites ? 'red' : 'gray'"
              label="Only my favourites"
              @click="toggleFavourites"
            />
          </template>
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

      <!--
        The way back out lives here, because the header it would otherwise live
        in does not exist when there are no rows — and "only my favourites"
        with nothing liked is exactly when you need the button that turns it
        off again.
      -->
      <EmptyState
        v-else-if="!rows.length"
        icon="lucide-inbox"
        :title="favourites ? 'Nothing here yet' : `No ${spec.view_label.toLowerCase()} yet`"
        :description="emptyBecause"
      >
        <template #action>
          <Button
            v-if="favourites"
            icon-left="lucide-heart-off"
            label="Show everything"
            @click="toggleFavourites"
          />
          <Button
            v-else-if="quickFilters.length || panelFilters.length"
            icon-left="lucide-filter-x"
            label="Clear the filters"
            @click="clearAllFilters"
          />
        </template>
      </EmptyState>

      <!-- Wide content owns its own horizontal scroller rather than stretching
           the page: a doctype with six columns does not fit a phone. -->
      <div v-else class="-mx-5 overflow-x-auto px-5 sm:mx-0 sm:px-0">
        <List
          :columns="tracks"
          :row-height="52"
          class="list-row-px-3 [&_[data-slot=list-header]]:bg-surface-gray-1"
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
              :class="c.pin && PINNED"
              :style="stickyStyle(c)"
              @click="sortBy(c.column.fieldname)"
            >
              <template #prefix>
                <Icon :name="c.column.icon" class="size-3.5 text-ink-gray-4" />
              </template>
              {{ c.header }}
            </ListHeaderCellSort>

            <!--
              How many, then the columns, then favourites. The heart is last so
              it sits directly above the one on every row.
            -->
            <ListHeaderCell
              v-if="metaColumn"
              :class="metaColumn.pin && PINNED"
              :style="stickyStyle(metaColumn)"
            >
              <span class="mr-auto whitespace-nowrap text-p-xs text-ink-gray-5">
                {{ counted }}
              </span>
              <Button
                icon="lucide-settings-2"
                variant="ghost"
                label="Choose columns"
                @click="showColumns = true"
              />
              <Button
                icon="lucide-heart"
                :variant="favourites ? 'subtle' : 'ghost'"
                :theme="favourites ? 'red' : 'gray'"
                label="Only my favourites"
                @click="toggleFavourites"
              />
            </ListHeaderCell>
          </ListHeader>

          <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
            <ListRow :value="value" @click="open(row)">
              <ListCell v-for="c in visible" :key="c.key" :class="c.pin && PINNED"
                :style="stickyStyle(c)">
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
// One model for every column. The title field renders with its avatar and id,
// activity renders its own cell, everything else is a value — but all three are
// entries in the same list, so all three can be moved, resized, pinned and
// dropped in the picker. That the title used to be a column the picker could
// not touch was a wart: it listed the field and removing it changed nothing.
const columnSpec = computed(() => {
  const titleField = spec.value?.title_field
  const chosen = columns.value || []

  // Where a pinned column starts, in pixels. A left pin sits past everything
  // pinned left before it; a right pin past everything pinned right after it.
  // Fixed widths are what make this computable at all.
  let fromLeft = 0
  const offsets = new Map()
  for (const column of chosen) {
    if (column.pin !== 'left') continue
    offsets.set(column.fieldname, fromLeft)
    fromLeft += column.width
  }
  let fromRight = 0
  for (const column of [...chosen].reverse()) {
    if (column.pin !== 'right') continue
    offsets.set(column.fieldname, fromRight)
    fromRight += column.width
  }

  return chosen.map((column, index) => ({
    key: column.fieldname,
    header: column.label,
    track: `${column.width}px`,
    // A phone shows the first two, and anything the reader pinned: pinning is
    // saying "keep this in view", which is truer on a small screen than a big
    // one.
    mobile: index < 2 || !!column.pin,
    cell:
      column.fieldname === META_FIELD
        ? 'meta'
        : column.fieldname === titleField
          ? 'title'
          : column.cell,
    sortable: column.fieldname !== META_FIELD,
    pin: column.pin,
    offset: offsets.get(column.fieldname) || 0,
    column,
  }))
})

const { visible, columns: tracks } = useListColumns(columnSpec)

// A list wide enough to scroll is exactly the list whose column picker you
// need, so the meta column is pinned to the right edge rather than scrolled off
// it. Opaque, or the columns it covers read through it.
// The server's name for the column that is not a field.
const META_FIELD = '__activity'

// A pinned column stops scrolling. Opaque, or the columns sliding under it read
// through it — and the offset is an inline style rather than a class because it
// is a computed pixel value, not a token.
const PINNED = 'sticky z-10 bg-surface-base'

const stickyStyle = (c) =>
  c.pin ? { [c.pin]: `${c.offset}px` } : undefined

const sortableColumns = computed(() => visible.value.filter((c) => c.cell !== 'meta'))
const metaColumn = computed(() => visible.value.find((c) => c.cell === 'meta') || null)

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

const clearAllFilters = () => {
  quickFilters.value = []
  panelFilters.value = []
  // The controls read their state from the spec, so re-resolving is what puts
  // the boxes back to empty rather than leaving them showing a cleared filter.
  load()
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
  // Unless the like is what the list is filtered by, in which case a row that
  // is no longer a favourite has no business still being in it.
  if (favourites.value) await loadRows()
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
    chosenColumns.value = (spec.value?.columns || []).map((c) => ({
      fieldname: c.fieldname,
      width: c.width,
      pin: c.pin,
    }))
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

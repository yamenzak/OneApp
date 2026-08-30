<template>
  <PageHeader>
    <div class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs" />
      <ViewSwitcher
        v-if="spec?.doctype"
        :layouts="spec.layouts || []"
        :active="spec.layout || ''"
        :screen-label="spec.screen_label"
        :can-share="!!spec.can_share"
        :busy="saving"
        @open="openLayout"
        @save-as="saveAs"
        @rename="renameLayout"
        @share="shareLayout"
        @default="defaultLayout"
        @remove="deleteLayout"
      />
    </div>
    <template v-if="spec?.can_create" #right>
      <Button variant="solid" icon-left="lucide-plus" label="New" @click="create" />
    </template>
  </PageHeader>

  <!--
    A pane, not a page. The route turns the shell's own scrolling off, so this
    fills the space under the header and the grid inside it owns both
    scrollbars — which is the whole point: a horizontal scrollbar at the bottom
    of a table is a scrollbar you have to scroll down to find, and on a list of
    two hundred rows nobody finds it.
  -->
  <div class="flex h-full min-h-0 flex-col p-5">
    <div v-if="loading" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!space"
      icon="lucide-circle-help"
      title="App not available"
      description="This space is not enabled for your workspace, or you do not have access to it."
    />

    <!--
      A screen the space wrote itself. Nothing else on the screen applies — and it
      gets its own scroll, because the pane does not scroll and a component we
      did not write cannot be assumed to fit.
    -->
    <div v-else-if="custom" class="min-h-0 flex-1 overflow-y-auto">
      <component :is="custom" :space-code="spaceCode" :screen="spec.screen" />
    </div>

    <!--
      An entitlement with no interface is a real thing to be: it still grants
      its roles and doctypes, and something else may be using them.
    -->
    <EmptyState
      v-else-if="!spec?.screens?.length"
      icon="lucide-hammer"
      title="Nothing to show yet"
      :description="`${space.space_label} is enabled for this workspace but has no screens.`"
    />

    <Alert v-else-if="spec.error" theme="amber" :title="spec.screen_label">
      <template #description>{{ spec.error }}</template>
    </Alert>

    <template v-else>
      <!--
        The quick boxes get a row of their own — Frappe's standard filter area.
        Most questions are "the open ones" rather than a filter builder, and a
        box you can type into beats a panel you have to open.
      -->
      <div class="mb-4 flex shrink-0 flex-col gap-2 sm:flex-row sm:items-start">
        <QuickFilters class="min-w-0 flex-1" :spec="spec" @changed="onQuickFilters" />
        <!-- Its own line on a phone. Beside a wrapping row of boxes the actions
             end up sitting on top of one. -->
        <div class="flex shrink-0 items-center gap-1">
          <FilterPanel
            :filters="panelFilters"
            :columns="spec.all_columns || []"
            :space-code="spaceCode"
            :screen="spec.screen"
            @changed="onPanelFilters"
          />
          <!--
            The gear is a question about the list, so it lives with the list's
            other controls. It used to sit in the activity column's header,
            which worked while that column was glued to the right edge — now
            that the table scrolls and every column is the reader's to move, a
            control parked in one of them can be somewhere off to the right.
            Frappe CRM draws the same line: Columns in the toolbar, the heart on
            its own column.
          -->
          <Button
            icon="lucide-settings-2"
            variant="ghost"
            label="Choose columns"
            tooltip="Choose columns"
            @click="showColumns = true"
          />
          <!--
            The heart is the exception, and stays in the activity header where
            it lines up with the one on every row — "filter by the ones I
            liked", directly above the likes. It comes here only when that
            column is not on the list at all. Never both, never neither.
          -->
          <Button
            v-if="!metaColumn"
            icon="lucide-heart"
            :variant="favourites ? 'subtle' : 'ghost'"
            :theme="favourites ? 'red' : 'gray'"
            label="Only my favourites"
            tooltip="Only my favourites"
            @click="toggleFavourites"
          />
          <Button
            v-if="dirty"
            icon-left="lucide-bookmark"
            label="Save this screen"
            :loading="saving"
            @click="saveLayout"
          />
          <Button
            v-if="spec.saved"
            icon="lucide-rotate-ccw"
            label="Back to the default screen"
            tooltip="Back to the default screen"
            variant="ghost"
            :loading="resetting"
            @click="resetLayout"
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

      <Alert v-else-if="rowsError" theme="red" title="This list could not be loaded">
        <template #description>{{ rowsError }}</template>
      </Alert>

      <!--
        The way back out lives here, because the header it would otherwise live
        in does not exist when there are no rows — and "only my favourites"
        with nothing liked is exactly when you need the button that turns it
        off again.
      -->
      <EmptyState
        v-else-if="!rows.length"
        icon="lucide-inbox"
        :title="favourites ? 'Nothing here yet' : `No ${spec.screen_label.toLowerCase()} yet`"
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

      <!--
        One surface, with its own horizontal scroller. A screen shows the same
        columns whatever the screen is — a phone scrolls the table sideways
        rather than being handed a different set of columns, because the columns
        are the reader's choice and a saved view that means something different
        on a phone is not a saved view.

        The border and the radius are the container's, so the header band ends
        in a rounded corner rather than a square one — and the band is why
        `ListHeader`'s own inset rule is off: a full-width fill under a rule
        that stops short on both sides is the "weird border" it read as.
      -->
      <!-- `relative` for the selection bar, which floats over the grid: the
           surface below clips its own overflow, so the bar has to be anchored
           outside it. -->
      <div v-else class="relative flex min-h-0 flex-1 flex-col">
        <div :class="SURFACE">
          <!--
            The body: how this screen is being looked at. A list today; a board
            or a calendar is a sibling component rather than a change here,
            because everything around it — the saved views, the filters, the
            selection, the footer — belongs to the screen rather than to the
            way it is drawn.
          -->
          <component
            :is="body"
            v-model:selection="selection"
            :spec="spec"
            :rows="rows"
            :columns="columns"
            :order-by="order || spec.order_by"
            :favourites="favourites"
            :counted="counted"
            :group-by="groupBy"
            @open="open"
            @like="like"
            @sort="sortBy"
            @columns="showColumns = true"
            @favourites="toggleFavourites"
          />

          <ListFooter
            :count="rows.length"
            :total="total"
            :page-length="pageLength"
            :sizes="spec.page_sizes || []"
            :has-more="hasMore"
            :loading="loadingMore"
            @more="loadMore"
            @page-length="setPageLength"
          />
        </div>

        <SelectionBar
          v-if="selection.length"
          :count="selection.length"
          :total="rows.length"
          @clear="selection = []"
          @all="selection = rows.map((row) => row.name)"
        >
          <Button
            v-if="spec.can_delete"
            theme="red"
            icon-left="lucide-trash-2"
            :label="`Delete ${selection.length}`"
            :loading="deleting"
            @click="confirmDelete = true"
          />
        </SelectionBar>
      </div>
    </template>
  </div>

  <!-- Deleting is the one thing on this screen that does not come back, so it
       asks — and says how many, because a selection is easy to lose track of. -->
  <Dialog
    v-model="confirmDelete"
    :title="`Delete ${selection.length} ${selection.length === 1 ? 'record' : 'records'}?`"
  >
    <p class="text-p-base text-ink-gray-7">
      This cannot be undone. Anything still linked to elsewhere will be kept and named.
    </p>
    <template #actions>
      <Button
        theme="red"
        variant="solid"
        :loading="deleting"
        label="Delete"
        @click="removeSelected"
      />
    </template>
  </Dialog>

  <ColumnPicker
    v-if="spec?.doctype"
    v-model="showColumns"
    :chosen="chosenColumns"
    :offered="spec.all_columns || []"
    :group-by="groupBy"
    @update:chosen="onColumns"
    @update:group-by="onGroupBy"
  />

  <RecordDialog
    v-if="spec?.doctype"
    v-model="showRecord"
    :record="editing || {}"
    :spec="spec"
    :space-code="spaceCode"
    :screen="spec.screen"
    @saved="loadRows"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  PageHeader,
  Breadcrumbs,
  Button,
  Alert,
  Skeleton,
  LoadingIndicator,
  Dialog,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import RecordDialog from '../components/screen/RecordDialog.vue'
import FilterPanel from '../components/screen/FilterPanel.vue'
import QuickFilters from '../components/screen/QuickFilters.vue'
import ColumnPicker from '../components/screen/ColumnPicker.vue'
import ListFooter from '../components/screen/ListFooter.vue'
import SelectionBar from '../components/screen/SelectionBar.vue'
import ViewSwitcher from '../components/screen/ViewSwitcher.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { notifyError, notifySuccess } from '../lib/notify'
import { screenComponent } from '../screens'
import { bodyFor } from '../lib/viewTypes'

const props = defineProps({ spaceCode: { type: String, required: true } })
const route = useRoute()
const router = useRouter()

const spec = ref(null)
const loading = ref(false)
const showRecord = ref(false)
const showColumns = ref(false)
const editing = ref(null)
const rows = ref([])
const columns = ref([])
const hasMore = ref(false)
const rowsLoading = ref(false)
const loadingMore = ref(false)
const rowsError = ref('')
// How many match, which the server counts once when a list opens. Null until
// it has: "48 of 0" while the answer is in flight is worse than "48".
const total = ref(null)
const pageLength = ref(100)
const saving = ref(false)
const resetting = ref(false)
const dirty = ref(false)
const deleting = ref(false)
const confirmDelete = ref(false)
// What is ticked. Cleared whenever the list is re-resolved, because a selection
// that outlives the rows it named is a selection of nothing.
const selection = ref([])

// The two filter surfaces are separate lists that are asked together, which is
// what Frappe does: the boxes above answer the common question and the panel
// answers the rest, and neither clears the other.
const quickFilters = ref([])
const panelFilters = ref([])
const order = ref('')
const chosenColumns = ref([])
const favourites = ref(false)
const groupBy = ref('')

const space = computed(() =>
  (session.spaces || []).find((one) => one.space_code === props.spaceCode),
)

// Which body draws this screen. Resolved from the type the server settled on,
// so an unknown or unbuilt one has already fallen back to the list before it
// reaches here.
const body = computed(() => bodyFor(spec.value?.view_type))

// Whether the body is showing the activity column, which is where the heart
// lives when it is: above the hearts on the rows, which is the only place the
// control and the thing it filters line up. When it is not — the reader
// dropped that column, or the body has no columns at all — the heart comes to
// the toolbar instead. Never both, never neither.
const META_FIELD = '__activity'
const metaColumn = computed(() =>
  (columns.value || []).some((column) => column.fieldname === META_FIELD),
)

const custom = computed(() => {
  const name = spec.value?.component
  return name ? screenComponent(name) : null
})



// The list's own chrome, kept out of the template so the token audit reads it:
// a class list in an attribute this long is unreadable, and one hidden in a
// string the audit cannot see is how `bg-surface-white` rendered a transparent
// column for a week.
//
// `rounded-6` is the panel radius — the same one every card on this surface
// uses. See `docs/SPACES.md` for the scale.
const SURFACE =
  'flex min-h-0 flex-1 flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base'

// The band behind the column headers, and the reason `ListHeader`'s own rule is
// off: that rule is a grid child inset to the content box, so under a
// full-width fill it stopped short at both ends. The band carries its own
// full-width rule instead.







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

// The trail stops at the space, because the switcher beside it is the next
// level: it opens on the screen's own name and every saved view of it, so a
// crumb saying the same word again is one word twice.
const crumbs = computed(() => {
  const trail = [{ label: 'Spaces', route: { name: 'Launcher' } }]
  if (space.value) trail.push({ label: space.value.app_label })
  if (!spec.value?.doctype && spec.value?.screen_label && spec.value.screens?.length > 1) {
    trail.push({ label: spec.value.screen_label })
  }
  return trail
})

// --- sorting, from the headers ----------------------------------------------
//
// The order belongs to the screen rather than to the body: it is saved with the
// view, it goes into every request, and a board sorts its cards by the same
// answer a list sorts its rows by. The body only says which column was clicked.

const sorted = computed(() => (order.value || spec.value?.order_by || '').split(' '))
const sortField = computed(() => sorted.value[0])
const ascending = computed(() => sorted.value[1] === 'asc')

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
  group_by: groupBy.value,
  page_length: pageLength.value,
})


// --- screens ------------------------------------------------------------------
//
// A screen is a named layout — filters, sort and columns saved together — which
// is the shape Frappe's own `List Filter` doctype settles on. Which one is open
// lives in the URL, so a screen is a link somebody can send.

const layout = computed(() => route.query.layout || '')

// Which way this screen is being looked at, from the URL. Empty means the
// screen's own first type, which is what the server falls back to — so a link
// without one is a link to the default rather than to nothing.
const viewType = computed(() => route.query.type || '')

const openLayout = (name) => {
  router.push({ query: { ...route.query, layout: name || undefined } })
}

const withView = async (work) => {
  saving.value = true
  try {
    const result = await work()
    await load(result?.layout)
    return result
  } finally {
    saving.value = false
  }
}

// Saved under a name, and opened straight away: the point of naming it is to
// be in it.
const saveAs = ({ label, shared }) =>
  withView(async () => {
    const result = await workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...payload(),
      label,
      shared,
    })
    dirty.value = false
    if (result?.layout) openLayout(result.layout)
    return result
  })

// A rename carries what is on screen with it, because the alternative is a
// rename that silently discards an unsaved change.
const renameLayout = ({ label, shared }) =>
  withView(() =>
    workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...payload(),
      layout: spec.value.layout,
      label,
      shared,
    }),
  )

const shareLayout = (shared) =>
  withView(() =>
    workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...payload(),
      layout: spec.value.layout,
      shared,
    }),
  )

const defaultLayout = () =>
  withView(() => workspace.defaultLayout(props.spaceCode, spec.value.screen, spec.value.layout))

const deleteLayout = async () => {
  const gone = spec.value.layout
  saving.value = true
  try {
    await workspace.deleteLayout(props.spaceCode, spec.value.screen, gone)
  } finally {
    saving.value = false
  }
  // Back to the screen's own declaration rather than to another screen: which
  // one would we pick?
  if (layout.value === gone) openLayout('')
  else await load()
}

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

const onGroupBy = (fieldname) => {
  groupBy.value = fieldname || ''
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
  const result = await workspace.toggleLike(props.spaceCode, spec.value.screen, row.name)
  // Patched in place rather than reloaded: a like is not a reason to lose the
  // reader's scroll position.
  row._meta = {
    ...row._meta,
    liked: !!result?.liked,
    likes: (result?.likes || []).length,
  }
  // Unless the like is what the list is filtered by, in which case a row that
  // is no longer a favourite has no business still being in it.
  if (favourites.value) await loadRows()
}

const removeSelected = async () => {
  deleting.value = true
  try {
    const result = await workspace.removeRecords(props.spaceCode, spec.value.screen, [
      ...selection.value,
    ])
    confirmDelete.value = false
    selection.value = (result?.refused || []).map((row) => row.name)
    if (result?.refused?.length) {
      // Named rather than counted: "3 could not be deleted" is not something a
      // person can act on, and the reason is usually a link somewhere else.
      notifyError(result.refused.map((row) => `${row.name}: ${row.reason}`).join('\n'))
    } else {
      notifySuccess(`Deleted ${result?.deleted?.length || 0}`)
    }
    await loadRows()
  } finally {
    deleting.value = false
  }
}

const fetchPage = (start) =>
  workspace.screenRows(
    props.spaceCode,
    spec.value.screen,
    payload(),
    spec.value.layout || '',
    { start, limit: pageLength.value },
    spec.value.view_type,
  )

const loadRows = async () => {
  if (!spec.value?.doctype) {
    rows.value = []
    columns.value = spec.value?.columns || []
    return
  }
  rowsLoading.value = true
  rowsError.value = ''
  try {
    const page = await fetchPage(0)
    rows.value = page?.rows || []
    selection.value = []
    // The columns the rows were actually fetched with, which is not always the
    // screen's: an unsaved change to the column list narrows the fetch, and a
    // header list that does not follow leaves a column standing over empty
    // cells.
    columns.value = page?.columns || spec.value.columns || []
    hasMore.value = !!page?.has_more
    countRows()
  } catch (error) {
    // A read that fails is not an empty list, and this one is asked quietly —
    // so without this a server error renders as "nothing here yet", which is
    // the most confidently wrong thing a screen can say. It cost an afternoon
    // once: a count query Frappe refused, shown as an empty backlog.
    rows.value = []
    total.value = null
    hasMore.value = false
    rowsError.value = error?.message || String(error)
  } finally {
    rowsLoading.value = false
  }
}

// Asked after the rows and never awaited with them: the footer says how many
// are loaded until this answers, and then how many there are.
let counting = 0
const countRows = async () => {
  const asked = ++counting
  total.value = null
  try {
    const answer = await workspace.screenRowCount(
      props.spaceCode,
      spec.value.screen,
      payload(),
      spec.value.layout || '',
    )
    // A count that arrives after the question changed is an answer to the old
    // question, and putting it in the footer is worse than leaving it blank.
    if (asked === counting) total.value = answer?.total ?? null
  } catch {
    // The rows are already on screen. A count that could not be taken leaves
    // the footer saying how many are loaded, which is true and is enough —
    // it is not a reason to shout at somebody reading a list.
  }
}

// Appends rather than replaces, and keeps the selection: someone who ticked
// four rows and then asked for more has not changed their mind about the four.
const loadMore = async () => {
  if (loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const page = await fetchPage(rows.value.length)
    const seen = new Set(rows.value.map((row) => row.name))
    rows.value = [...rows.value, ...(page?.rows || []).filter((row) => !seen.has(row.name))]
    hasMore.value = !!page?.has_more
  } finally {
    loadingMore.value = false
  }
}

// A page size is part of the screen, so changing it is a change to save like any
// other — and it starts the list again rather than truncating what is loaded.
const setPageLength = (size) => {
  if (!size || size === pageLength.value) return
  pageLength.value = size
  changed()
}

const saveLayout = async () => {
  saving.value = true
  try {
    await workspace.saveLayout(props.spaceCode, spec.value.screen, payload())
    dirty.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const resetLayout = async () => {
  resetting.value = true
  try {
    await workspace.resetLayout(props.spaceCode, spec.value.screen)
    dirty.value = false
    await load()
  } finally {
    resetting.value = false
  }
}

const load = async (openWith) => {
  if (!space.value) return
  loading.value = true
  try {
    spec.value = await workspace.screenSpec(
      props.spaceCode,
      route.query.screen || '',
      openWith || layout.value,
      viewType.value || undefined,
    )
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
    groupBy.value = spec.value?.saved?.group_by || ''
    pageLength.value = spec.value?.page_length || 100
    dirty.value = false
    await loadRows()
  } finally {
    loading.value = false
  }
}


// Re-resolved on every screen change: the columns, the filters and what this user
// may do are all per screen, not per space.
watch(
  [
    () => props.spaceCode,
    () => route.query.screen,
    () => route.query.type,
    () => route.query.layout,
    () => session.loaded,
  ],
  () => load(),
  { immediate: true },
)
</script>

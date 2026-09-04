<template>
  <ScreenHeader
    :spec="spec"
    :crumbs="crumbs"
    :record-crumb="recordCrumb"
    :view-label="viewLabel"
    :status-value="statusValue"
    :doc-state="docState"
    :record="shownRecord"
    :page="asPage"
    :dirty="dirty"
    :saving="saving"
    :views="views"
    @create="create"
  />

  <!--
    A pane, not a page. The route turns the shell's own scrolling off, so this
    fills the space under the header and the grid inside it owns both
    scrollbars — which is the whole point: a horizontal scrollbar at the bottom
    of a table is a scrollbar you have to scroll down to find, and on a list of
    two hundred rows nobody finds it.
  -->
  <div class="flex h-full min-h-0">
   <!--
     `v-show` and not `v-if`: on a showcase screen the record takes the whole
     area and the list goes away, but it goes away the way a covered thing does
     — closing the record comes back to the same rows, the same scroll position
     and the same unsaved filter, rather than to a screen that fetches itself
     again.
   -->
   <div v-show="!asPage" class="flex min-w-0 flex-1 flex-col p-5">
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

    <Alert v-else-if="specError" theme="red" title="This screen could not be opened">
      <template #description>{{ specError }}</template>
    </Alert>

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
      <!--
        One row at every width. On a phone that is the ID box taking the width
        and two controls at its end — reveal the rest of the boxes, open the
        filter panel — which is the shape Frappe's mobile list uses and the
        reason the boxes no longer carry their own chevron.
      -->
      <div class="mb-4 flex shrink-0 items-start gap-2">
        <QuickFilters
          v-model:expanded="quickExpanded"
          class="min-w-0 flex-1"
          :spec="spec"
          @changed="onQuickFilters"
          @overflow="quickOverflow = $event"
        />
        <div class="flex shrink-0 items-center gap-1">
          <!-- Only when there is something to reveal, which the row works out
               by measuring itself: five boxes fit across a full-width list and
               two beside an open record, and the chevron is how the other
               three are reached at either width. -->
          <Button
            v-if="quickOverflow || quickExpanded"
            :icon="quickExpanded ? 'lucide-chevron-up' : 'lucide-chevron-down'"
            :label="quickExpanded ? 'Fewer filters' : 'More filters'"
            :tooltip="quickExpanded ? 'Fewer filters' : 'More filters'"
            :variant="quickExpanded ? 'subtle' : 'ghost'"
            @click="quickExpanded = !quickExpanded"
          />
          <!--
            The column picker is not here. It lives in the footer beside the
            count: both are questions about the table rather than about the
            rows, and this row is the one people type in — a fourth control
            beside the box is the clutter, not the answer.
          -->
          <FilterPanel
            :filters="panelFilters"
            :columns="spec.all_columns || []"
            :space-code="spaceCode"
            :screen="spec.screen"
            @changed="onPanelFilters"
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
          <!--
            The pair that appears when there is something unsaved, and the
            same pair whether "saved" means into a named view or into this
            person's own default — one decision, made in `savesIntoView`,
            rather than two controls that look alike and do different things.
          -->
          <Button
            v-if="dirty"
            icon-left="lucide-bookmark"
            :label="saveLabel"
            :loading="saving"
            @click="saveLayout"
          />
          <Button
            v-if="dirty || spec.saved"
            icon="lucide-rotate-ccw"
            :label="discardLabel"
            :tooltip="discardLabel"
            variant="ghost"
            :loading="resetting"
            @click="discardChanges"
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
            :group-by="groupedBy"
            :board="fetchedBoard || spec.board || {}"
            :cards="fetchedCards || spec.cards || {}"
            :space-code="spaceCode"
            :layout="spec.layout || ''"
            :overrides="dashboardAsked"
            @open="open"
            @like="like"
            @sort="sortBy"
            @favourites="toggleFavourites"
            @change="writeField"
            @new="newWith"
          />

          <!-- A dashboard measures every row that matches rather than drawing
               a page of them, so page sizes, "43 of 43" and Load more are
               three controls about something it is not doing. -->
          <ListFooter
            v-if="spec.view_type !== 'dashboard'"
            :count="rows.length"
            :total="total"
            :page-length="pageLength"
            :sizes="spec.page_sizes || []"
            :has-more="hasMore"
            :loading="loadingMore"
            @more="loadMore"
            @page-length="setPageLength"
            :view-type="spec.view_type"
            @columns="openSettings"
          />
        </div>

        <SelectionBar
          v-if="selection.length"
          :count="selection.length"
          :total="rows.length"
          @clear="selection = []"
          @all="selection = rows.map((row) => row.name)"
        >
          <!-- What the screen declares for a selection — replaying a batch of
               webhook events, say. Before Delete, because Delete is the one
               that does not come back and belongs at the end. -->
          <ScreenActions
            :actions="spec.actions || []"
            scope="selection"
            :space-code="spaceCode"
            :screen="spec.screen"
            :names="selection"
            @ran="loadRows"
          />
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

    <!--
      The open record, beside the list rather than over it. A record is
      something you read *against* the list — mark this one done, glance at the
      next, come back — and a modal takes the list away and the page out of the
      accessibility tree with it. On a phone there is no room to keep both, so
      the pane draws itself as a page; it decides that, not this file.
    -->
    <RecordPane v-if="shownRecord && spec?.doctype" :page="asPage">
      <template #body="{ phone }">
        <RecordView
          :record="shownRecord"
          :spec="spec"
          :space-code="spaceCode"
          :screen="spec.screen"
          :phone="phone"
          :surface="asPage ? PAGE : PANE"
          :revision="childRevision"
          @saved="recordSaved"
          @reload="reloadRecord"
          @close="closeRecord"
          @renamed="recordRenamed"
          @open="openElsewhere"
          @surface="setSurface"
          @add="addChild"
        />
      </template>
    </RecordPane>

    <!--
      A record opened *from* the one on screen: a variation from the job it
      hangs off, an invoice from the project it was raised against. Over the
      page rather than instead of it, because the thing you came from is the
      reason you are looking at this one.

      Its own spec and its own record, because it is usually another screen —
      an invoice drawn through the projects screen's columns is not an invoice.
    -->
    <RecordDrawer v-if="peeked && peekSpec?.doctype" @close="closePeek">
      <RecordView
        :record="peeked"
        :spec="peekSpec"
        :space-code="spaceCode"
        :screen="peekSpec.screen"
        :surface="DRAWER"
        @saved="peekSaved"
        @reload="loadPeek"
        @close="closePeek"
        @renamed="peekRenamed"
        @open="openElsewhere"
        @expand="expandPeek"
      />
    </RecordDrawer>
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

  <CardSettings
    v-if="spec?.doctype"
    v-model="showCards"
    :spec="spec"
    :view-type="spec.view_type"
    :board="fetchedBoard || spec.board || {}"
    :cards="fetchedCards || spec.cards || {}"
    @changed="cardsChanged"
  />

  <ColumnPicker
    v-if="spec?.doctype"
    v-model="showColumns"
    :chosen="chosenColumns"
    :offered="spec.all_columns || []"
    :group-by="groupBy"
    @update:chosen="onColumns"
    @update:group-by="onGroupBy"
  />

  <!--
    Making a record. Usually this screen's, and sometimes another's: the plus on
    a showcase's rail makes what hangs off the record being read, and what hangs
    off a record can be a different screen entirely — so the dialog is given
    whichever spec it is filling in. See `onto`.
  -->
  <CreateDialog
    v-if="createSpec?.doctype"
    v-model="showCreate"
    :spec="createSpec"
    :space-code="spaceCode"
    :screen="createScreen"
    :preset="preset"
    @created="created"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Button,
  Alert,
  Skeleton,
  LoadingIndicator,
  Dialog,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import ScreenHeader from '../components/screen/ScreenHeader.vue'
import CreateDialog from '../components/screen/CreateDialog.vue'
import RecordPane from '../components/screen/RecordPane.vue'
import RecordView from '../components/screen/RecordView.vue'
import RecordDrawer from '../components/screen/RecordDrawer.vue'
import FilterPanel from '../components/screen/FilterPanel.vue'
import QuickFilters from '../components/screen/QuickFilters.vue'
import CardSettings from '../components/screen/CardSettings.vue'
import ColumnPicker from '../components/screen/ColumnPicker.vue'
import ListFooter from '../components/screen/ListFooter.vue'
import SelectionBar from '../components/screen/SelectionBar.vue'
import ScreenActions from '../components/screen/ScreenActions.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { useCreating } from '../composables/useCreating'
import { useCrumbs } from '../composables/useCrumbs'
import { useListFollow } from '../composables/useListFollow'
import { usePeek } from '../composables/usePeek'
import { useRecordSurface } from '../composables/useRecordSurface'
import { useRows } from '../composables/useRows'
import { useSavedViews } from '../composables/useSavedViews'
import { useSorting } from '../composables/useSorting'
import { notifyError, notifySuccess } from '../lib/notify'
import { screenComponent } from '../screens'
import { CARD_VIEW_TYPES, DEFAULT_VIEW_TYPE, bodyFor } from '../lib/viewTypes'
import { applyTheme, clearTheme } from '../lib/theme'
import { DRAWER, PAGE, PANE } from '../lib/surfaces'

const props = defineProps({ spaceCode: { type: String, required: true } })
const route = useRoute()
const router = useRouter()

// Whether the phone is showing the quick boxes past the first. The toolbar
// owns the control, the boxes own the rendering.
const quickExpanded = ref(false)
// Whether the row is holding boxes back, which only it can know: it measures
// itself against the width the pane leaves it.
const quickOverflow = ref(false)

const spec = ref(null)

// Making a record — `composables/useCreating.js`. `reloadList` is a thunk
// because `loadRows` comes from `useRows`, further down.
const {
  showCreate, preset, childRevision, createSpec, createScreen,
  create, newWith, addChild, created,
} = useCreating({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  reloadList: () => loadRows(),
})

// The record this screen has open, and whether it is a pane or the page —
// `composables/useRecordSurface.js`. Above `usePeek` and `useCrumbs` because
// both read `shownRecord`.
const {
  shownRecord, asPage, setSurface,
  open, openElsewhere, openRecord, closeRecord,
  reloadRecord, recordSaved, recordRenamed,
} = useRecordSurface({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  reloadList: () => loadRows(),
})
const loading = ref(false)
const showColumns = ref(false)
const showCards = ref(false)

// One gear, two dialogs. Which one is the body's question, not the footer's:
// a card view has no column widths and a list has no cards.
const openSettings = () => {
  if (CARD_VIEW_TYPES.includes(spec.value?.view_type)) showCards.value = true
  else showColumns.value = true
}

// What the reader has said about a card view and not yet saved. Empty until
// they touch it, so the screen's own answer stands — the same shape the
// filters and the sort use, and it rides in the same payload.
//
// Keyed by view type, the shape the manifest and a saved view both store: a
// board's card and a grid's card are separate answers, and switching between
// the two views should not carry one over the other.
const viewSettings = ref({})

const cardsChanged = (changes) => {
  const type = spec.value?.view_type || DEFAULT_VIEW_TYPE
  viewSettings.value = {
    ...viewSettings.value,
    [type]: { ...(viewSettings.value[type] || {}), ...changes },
  }
  changed()
}
// Why the screen would not resolve at all — a different failure from a list
// that would not load, and the one that used to read as "no screens".
const specError = ref('')
const saving = ref(false)
const resetting = ref(false)
const dirty = ref(false)
const deleting = ref(false)
const confirmDelete = ref(false)

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
// uses. See `docs/ONESPACE.md` for the scale.
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

// A record opened from inside another one, in `composables/usePeek.js`.
const {
  peeked, peekSpec,
  closePeek, peekSaved, expandPeek, peekRenamed,
} = usePeek({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  // A thunk: `loadRows` is defined below this call.
  reloadList: () => loadRows(),
})

/**
 * The space's own look, on the document while this space is open.
 *
 * Read from the session's own list of spaces rather than from `spec`, and that
 * is deliberate: the session is already in hand when the route resolves, so a
 * themed space arrives themed instead of painting one light frame and then
 * turning dark. See `lib/theme.js` for what a declaration moves.
 *
 * Taken off on the way out. A space's personality is that space's — the
 * launcher, the account area and the next space are not it.
 */
watch(
  () => props.spaceCode,
  (code) => {
    const space = session.spaces.find((one) => one.space_code === code)
    applyTheme(space?.theme)
  },
  { immediate: true },
)

onBeforeUnmount(clearTheme)


// The order the list is in — `composables/useSorting.js`.
const { sortBy } = useSorting({ order, spec, onChange: () => changed() })

// --- what the list is being asked -------------------------------------------

const payload = () => ({
  // Which way of looking this view is of. Without it every save landed on the
  // screen's *first* type, so a view saved from the board was filed as a list
  // view and never appeared in the board's own switcher again.
  view_type: spec.value?.view_type || DEFAULT_VIEW_TYPE,
  filters: [...quickFilters.value, ...panelFilters.value],
  order_by: order.value,
  columns: chosenColumns.value,
  favourites: favourites.value,
  group_by: groupBy.value,
  page_length: pageLength.value,
  // Nested by view type, the same shape the manifest uses and the same shape a
  // saved view stores. Sent whole so that clearing a choice clears it: a
  // truthiness check would leave the last board field standing after a reset.
  view_settings: viewSettings.value,
})


/**
 * What a dashboard is narrowed by, as a value that changes when the filters do.
 *
 * The same `payload()` the rows go through, so the charts and the list are
 * answering one question — but only the parts that decide *which records*.
 * Columns, widths and what a card carries are about drawing, and a chart that
 * re-fetched when somebody widened a column would be re-fetching for nothing.
 *
 * A computed rather than a call, because the body watches it: a function
 * returning a fresh object every render is a watcher that never settles.
 */
const dashboardAsked = computed(() => ({
  filters: [...quickFilters.value, ...panelFilters.value],
  order_by: order.value,
  favourites: favourites.value,
}))


// --- screens ------------------------------------------------------------------
//
// A screen is a named layout — filters, sort and columns saved together — which
// is the shape Frappe's own `List Filter` doctype settles on. Which one is open
// lives in the URL, so a screen is a link somebody can send.

// Saved views — `composables/useSavedViews.js`. Kept whole as well as
// destructured: `ScreenHeader` takes the object, because the switcher's menu
// is exactly this composable and forwarding its nine verbs one event at a time
// says nothing that `:views="views"` does not.
const views = useSavedViews({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  saving,
  dirty,
  // Thunks: both are defined below this call.
  payload: () => payload(),
  reload: (into) => load(into),
})
const { layout } = views


// Which way this screen is being looked at, from the URL. Empty means the
// screen's own first type, which is what the server falls back to — so a link
// without one is a link to the default rather than to nothing.
const viewType = computed(() => route.query.type || '')

// Where the reader is, as the header draws it — `composables/useCrumbs.js`.
const { viewLabel, crumbs, recordCrumb, statusValue, docState } = useCrumbs({
  spaceCode: props.spaceCode,
  spec,
  space,
  shownRecord,
  viewType,
})

const changed = async () => {
  dirty.value = true
  await loadRows()
}

// The list follows the site — `composables/useListFollow.js`.
const { follow } = useListFollow({ paused: dirty, reload: () => loadRows() })

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

// One field, written from a body, without opening the record.
//
// A board's whole reason to exist: dragging a card between columns is a save
// of the field the columns are. Optimistic on the row so the card stays where
// it was dropped while the request is in flight, then the list is re-read —
// the save may have changed more than was sent (a workflow, a fetch_from, a
// `modified` that reorders the page), and a board showing our guess instead of
// the server's answer is a board that lies quietly.
const writeField = async ({ row, field, value }) => {
  if (!row || !field) return
  const was = row[field]
  row[field] = value
  try {
    await workspace.saveRecord(props.spaceCode, spec.value.screen, { [field]: value }, row.name)
  } catch (e) {
    row[field] = was
    notifyError(e.message || String(e))
    return
  }
  await loadRows()
}

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

// The records this screen lists — `composables/useRows.js`.
const {
  rows, columns, selection, total, hasMore, rowsLoading, loadingMore,
  rowsError, pageLength, groupedBy, fetchedBoard, fetchedCards,
  loadRows, loadMore, setPageLength,
} = useRows({
  spaceCode: props.spaceCode,
  spec,
  // Thunks: both are defined below this call.
  payload: () => payload(),
  onChange: () => changed(),
})

// Where an unsaved change goes when you say to keep it, which depends on where
// you are. In a named view you may write, it goes into that view; anywhere
// else it goes into this person's own unnamed default for the screen, which is
// what "keep this how I left it" has always meant.
//
// Frappe CRM draws the same line — Save Changes appears only on a view you may
// write — and the alternative is worse in both directions: a Save that
// silently makes a private copy of a shared view, or one that quietly rewrites
// a view other people are using.
//
// "In a named view" and not merely "a layout is open": this person's own
// unnamed default is a layout row too, and the screen opens with it — so
// reading `spec.layout` alone made Save write into the default it had just
// resolved and left Discard with nothing to reset. The label is what makes a
// layout a view somebody named.
const currentLayout = computed(
  () => (spec.value?.layouts || []).find((l) => l.name === spec.value?.layout) || null,
)

const savesIntoView = computed(
  () => !!currentLayout.value?.label && (currentLayout.value.mine || !!spec.value?.can_share),
)

const saveLabel = computed(() => (savesIntoView.value ? 'Save changes' : 'Save this screen'))

const discardLabel = computed(() =>
  dirty.value ? 'Discard these changes' : 'Back to the default screen',
)

const saveLayout = async () => {
  saving.value = true
  try {
    await workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...payload(),
      ...(savesIntoView.value ? { layout: spec.value.layout } : {}),
    })
    dirty.value = false
    await load()
  } finally {
    saving.value = false
  }
}

// The way back. In a view that means the view as it was saved — a reload of
// the same layout, which is what `load()` does; on the screen itself it means
// dropping this person's saved default altogether.
const discardChanges = async () => {
  resetting.value = true
  try {
    if (!savesIntoView.value && spec.value?.saved) {
      await workspace.resetLayout(
        props.spaceCode, spec.value.screen, spec.value.view_type,
      )
    }
    dirty.value = false
    await load()
  } finally {
    resetting.value = false
  }
}

/**
 * What the reader has asked of the *rows*, as it stands.
 *
 * The distinction this turns on is one the reader already makes: a filter, a
 * sort and "only my favourites" are questions about **which records**, and
 * columns, widths, pinning, grouping and what a card carries are questions
 * about **how they are drawn**. Switching from a list to a board changes the
 * second and not the first — "only the open ones, by priority" is the same
 * question drawn as columns — so that is what crosses over.
 *
 * Only when the switch happens under somebody. Opening a link cold is not
 * carrying anything, so it gets that view type's own default, which is what a
 * link should mean.
 */
const askedOfRows = () => ({
  quick: quickFilters.value.map((one) => [...one]),
  panel: panelFilters.value.map((one) => [...one]),
  order: order.value,
  favourites: favourites.value,
})

const sameRows = (a, b) => JSON.stringify(a) === JSON.stringify(b)

const load = async (openWith, carry = null) => {
  if (!space.value) return
  loading.value = true
  specError.value = ''
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
    // Whatever was said about a card and not saved. Cleared with the rest of
    // the unsaved state: it was said about the view that was open, and opening
    // another one — a saved view, or a different type — is not a reason to
    // keep overriding what that one resolved to.
    viewSettings.value = {}
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
    drawnAs.value = {
      screen: spec.value?.screen || '',
      type: spec.value?.view_type || '',
    }

    // What the reader was asking of the rows before the view type changed
    // under them, applied over what this type resolved to — and marked unsaved
    // where the two differ, so the switcher says "this view, with changes"
    // rather than showing a filtered board under a view's name that means
    // something else.
    if (carry) {
      const resolved = askedOfRows()
      quickFilters.value = carry.quick
      panelFilters.value = carry.panel
      order.value = carry.order || order.value
      favourites.value = carry.favourites
      dirty.value = !sameRows(carry, resolved)
    }
    follow(spec.value?.doctype || '')
    await loadRows()
  } catch (err) {
    // A screen that will not resolve is not a screen with nothing on it. The
    // spec is fetched silently, so a refused one used to leave `spec` null and
    // fall through to "this space has no screens" — which sent us looking at
    // the manifest for an hour while the real answer, a permission the fixture
    // had not written, was in the response body all along.
    spec.value = null
    specError.value = err?.message || String(err)
  } finally {
    loading.value = false
  }
}


// Re-resolved on every screen change: the columns, the filters and what this user
// may do are all per screen, not per space.
// What the last render was actually of — the screen, and the way of looking the
// server settled on, which is not always the one the URL asked for. Only a
// change of view type carries anything: another screen is another set of
// records and has nothing to carry.
const drawnAs = ref({ screen: '', type: '' })

watch(
  [
    () => props.spaceCode,
    () => route.query.screen,
    () => route.query.type,
    () => route.query.layout,
    () => session.loaded,
  ],
  () => {
    // Not when a named view is being opened: a view carries its own answers,
    // and the point of opening one is to see them.
    const switching =
      !!spec.value &&
      !!drawnAs.value.type &&
      drawnAs.value.screen === (route.query.screen || spec.value.screen) &&
      !route.query.layout
    load(undefined, switching ? askedOfRows() : null)
  },
  { immediate: true },
)

// Its own watch, and after the spec: opening a record by id needs the screen
// resolved first, and the two change independently — clicking a row changes
// only this, and switching view changes only that.
//
// Never on a component screen. There is no list and no record pane there, so
// `?record=` means whatever that component decided it means — the operator
// console uses it to say which workspace it is showing. Left to run, this
// fetched a record the screen does not list, found nothing, and cleaned the
// parameter out of the URL: a link straight to a workspace opened empty, and
// only arriving from the list worked.
watch([() => route.query.record, () => spec.value?.screen], ([name, screen]) => {
  if (screen && !spec.value?.component) openRecord(name || '')
})
</script>

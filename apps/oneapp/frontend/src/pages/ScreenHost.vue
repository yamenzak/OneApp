<template>
  <PageHeader>
    <!--
      Frappe CRM's trail, and its shape is the argument: a house for the space,
      the screen, and then the thing you are actually looking at — which is the
      view, or the record when one is open. The space's name is the house's
      tooltip rather than a word in the line, because the rail already says
      which space this is and the trail has one line to spend.
    -->
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs">
        <template #prefix="{ item }">
          <!--
            The name is a span, not the icon's `aria-label`: frappe-ui's Icon
            hard-codes `aria-hidden` after the attrs it forwards, which is the
            right call — an icon is decoration — and it leaves a link whose
            only content is one with no accessible name at all.
          -->
          <Tooltip v-if="item.home" :text="`${item.space} home`">
            <span class="flex items-center">
              <Icon name="lucide-house" class="size-4 text-ink-gray-5" />
              <span class="sr-only">{{ item.space }} home</span>
            </span>
          </Tooltip>
        </template>
      </Breadcrumbs>

      <!--
        A record is a record wherever it is shown: the same face, name and id
        the list cell and the link picker draw, from the same component — with
        the status beside the name, because "where does this stand" is the
        second thing anybody asks about a record and the first thing they look
        for.

        Its own element rather than a crumb, for the same reason the view
        switcher is one: a crumb is a line of text, and this is a block two
        lines tall.
      -->
      <div v-if="recordCrumb" class="flex min-w-0 items-center">
        <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
        <RecordChip :record="recordCrumb">
          <template #badge>
            <!-- The colours are the doctype's own Document States — the same
                 ones the cell in the list reads — so a status is not one
                 colour here and another there. The manifest says which field;
                 it does not repeat the palette. -->
            <Badge
              v-if="statusValue"
              data-slot="record-status"
              :label="String(statusValue)"
              :theme="statusTheme"
              variant="subtle"
            />
          </template>
        </RecordChip>
      </div>

      <!-- The last crumb, when no record is open: which view of the screen
           this is, and every other view of it. -->
      <ViewSwitcher
        v-if="spec?.doctype && !shownRecord"
        :layouts="spec.layouts || []"
        :active="spec.layout || ''"
        :view-label="viewLabel"
        :can-share="!!spec.can_share"
        :dirty="dirty"
        :hidden="spec.hidden || 0"
        :busy="saving"
        @open="openLayout"
        @save-as="saveAs"
        @save-into="saveIntoLayout"
        @rename="renameLayout"
        @share="shareLayout"
        @default="defaultLayout"
        @remove="deleteLayout"
        @hide="hideLayout"
        @show="showLayouts"
      />
    </nav>

    <!--
      In the default slot, not a `#right` one: PageHeader has exactly one slot
      and lays it out as a `justify-between` row, so the trail goes left and
      this goes right by being second. It spent this long in a slot that does
      not exist, rendering nowhere — `test_no_unknown_slots` now catches the
      shape that hid it.
    -->
    <Button
      v-if="spec?.can_create"
      variant="solid"
      icon-left="lucide-plus"
      label="New"
      @click="create"
    />
  </PageHeader>

  <!--
    A pane, not a page. The route turns the shell's own scrolling off, so this
    fills the space under the header and the grid inside it owns both
    scrollbars — which is the whole point: a horizontal scrollbar at the bottom
    of a table is a scrollbar you have to scroll down to find, and on a list of
    two hundred rows nobody finds it.
  -->
  <div class="flex h-full min-h-0">
   <div class="flex min-w-0 flex-1 flex-col p-5">
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
        />
        <div class="flex shrink-0 items-center gap-1">
          <Button
            class="sm:hidden"
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
    <RecordPane v-if="shownRecord && spec?.doctype">
      <template #body="{ phone }">
        <RecordView
          :record="shownRecord"
          :spec="spec"
          :space-code="spaceCode"
          :screen="spec.screen"
          :phone="phone"
          @saved="recordSaved"
          @reload="reloadRecord"
          @close="closeRecord"
          @renamed="recordRenamed"
        />
      </template>
    </RecordPane>
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

  <CreateDialog
    v-if="spec?.doctype"
    v-model="showCreate"
    :spec="spec"
    :space-code="spaceCode"
    :screen="spec.screen"
    :preset="preset"
    @created="created"
  />
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  PageHeader,
  Breadcrumbs,
  Badge,
  Icon,
  Tooltip,
  Button,
  Alert,
  Skeleton,
  LoadingIndicator,
  Dialog,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import RecordChip from '../components/screen/RecordChip.vue'
import CreateDialog from '../components/screen/CreateDialog.vue'
import RecordPane from '../components/screen/RecordPane.vue'
import RecordView from '../components/screen/RecordView.vue'
import FilterPanel from '../components/screen/FilterPanel.vue'
import QuickFilters from '../components/screen/QuickFilters.vue'
import CardSettings from '../components/screen/CardSettings.vue'
import ColumnPicker from '../components/screen/ColumnPicker.vue'
import ListFooter from '../components/screen/ListFooter.vue'
import SelectionBar from '../components/screen/SelectionBar.vue'
import ScreenActions from '../components/screen/ScreenActions.vue'
import ViewSwitcher from '../components/screen/ViewSwitcher.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { notifyError, notifySuccess } from '../lib/notify'
import { screenComponent } from '../screens'
import { CARD_VIEW_TYPES, DEFAULT_VIEW_TYPE, VIEW_TYPES, bodyFor } from '../lib/viewTypes'
import { onDoctypeChange } from '../lib/socket'
import { valueTheme } from '../lib/fields'

const props = defineProps({ spaceCode: { type: String, required: true } })
const route = useRoute()
const router = useRouter()

// Whether the phone is showing the quick boxes past the first. The toolbar
// owns the control, the boxes own the rendering.
const quickExpanded = ref(false)

const spec = ref(null)
const loading = ref(false)
const showCreate = ref(false)
// What the create dialog opens with already filled in. Empty for the toolbar's
// New; a status for a board column's.
const preset = ref({})
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
// The record that is open, fetched. Null is "no record", which is also what
// closing one means — there is no second flag, because two of them is how a
// pane ends up open over nothing.
const editing = ref(null)
const rows = ref([])
const columns = ref([])
const hasMore = ref(false)
const rowsLoading = ref(false)
const loadingMore = ref(false)
const rowsError = ref('')
// Why the screen would not resolve at all — a different failure from a list
// that would not load, and the one that used to read as "no screens".
const specError = ref('')
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
// The same question, answered by the last page that arrived rather than by the
// control. See `loadRows`.
const groupedBy = ref('')
// The board the last page came back for. Null until one has, which is when the
// screen's own answer stands.
const fetchedBoard = ref(null)
// And what a card says, for the same reason: a chosen card field changes what
// is fetched, so drawing the new card before its rows arrive is a card of
// empty fields for as long as the request takes.
const fetchedCards = ref(null)

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

// A record that exists takes the last place in the trail. A record being made
// does not, and never reaches here: it is a dialog, and there is nothing to
// name it with yet.
const shownRecord = computed(() => editing.value)

// What the last crumb says when no view is saved: how this screen is being
// drawn. "Tasks / Tasks" is one word twice; "Tasks / List" says where you are.
const viewLabel = computed(() => {
  const type = spec.value?.view_type || DEFAULT_VIEW_TYPE
  return VIEW_TYPES[type]?.label || 'List'
})

// The space's first screen, which is what the house goes to. A space home is a
// page of its own one day; until it is, the first thing in the navigation is
// the nearest true thing.
const homeRoute = computed(() => {
  const first = spec.value?.screens?.[0]
  return {
    name: 'Screen',
    params: { spaceCode: props.spaceCode },
    ...(first ? { query: { screen: first.screen } } : {}),
  }
})

const crumbs = computed(() => {
  if (!space.value) return []
  const trail = [{ label: '', home: true, space: space.value.space_label, route: homeRoute.value }]
  if (spec.value?.screen_label) {
    trail.push({
      label: spec.value.screen_label,
      route: {
        name: 'Screen',
        params: { spaceCode: props.spaceCode },
        query: { screen: spec.value.screen },
      },
    })
  }
  return trail
})

// The record, when one is open. It is where you are, so it takes the last
// place from the view.
//
// Worth being honest about what this is not yet: the record opens as a modal
// dialog, and a modal takes the rest of the page out of the accessibility
// tree, so while it is open this can be read by eye and not by a screen
// reader. What it does buy today is the URL — a record is a link somebody can
// send — and it is the trail a record *page* will want when there is one.
const recordCrumb = computed(() => {
  const open = shownRecord.value
  if (!open) return null
  const title = spec.value?.title_field
  const label = (title && open[title]) || open.name
  return {
    value: open.name,
    label: String(label),
    // The id, and only where the name is not already it.
    id: label === open.name ? '' : open.name,
    image: spec.value?.image_field ? open[spec.value.image_field] : null,
  }
})

// Where the record stands. Which field that is comes from the manifest and is
// checked against the doctype on the way out; what colour it is comes from the
// doctype's own states, the same way the list cell reads it.
const statusValue = computed(() => {
  const field = spec.value?.status_field
  return (field && shownRecord.value?.[field]) || ''
})

const statusTheme = computed(() => valueTheme(statusValue.value, spec.value?.states || []))

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
const saveAs = ({ label, icon, shared }) =>
  withView(async () => {
    const result = await workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...payload(),
      label,
      icon,
      shared,
    })
    dirty.value = false
    if (result?.layout) openLayout(result.layout)
    return result
  })

// Every one of these names the view it acts on rather than assuming the one on
// screen: the menu manages all of them now, so "rename" can mean a view this
// person is not looking at.
//
// What is on screen goes with a write only when it is meant to. Renaming the
// view you are looking at carries it, because the alternative is a rename that
// silently discards an unsaved change; renaming some *other* view must not,
// because that would put this screen's filters into a view nobody was editing.
// Saving into a view carries it either way — that is what saving into it is.
const intoLayout = (name, extra, carry = name === spec.value.layout) =>
  withView(() =>
    workspace.saveLayout(props.spaceCode, spec.value.screen, {
      ...(carry ? payload() : {}),
      layout: name,
      ...extra,
    }),
  )

const renameLayout = ({ layout: name, label, icon, shared }) =>
  intoLayout(name, { label, icon, shared })

const shareLayout = ({ layout: name, shared }) => intoLayout(name, { shared })

// The other half of Save: put what is on screen into a view that already
// exists rather than into a new one. Only offered for a view you may write.
const saveIntoLayout = async (name) => {
  await intoLayout(name, {}, true)
  dirty.value = false
  if (name !== spec.value.layout) openLayout(name)
}

const defaultLayout = (name) =>
  withView(() => workspace.defaultLayout(props.spaceCode, spec.value.screen, name))

const deleteLayout = async (name) => {
  saving.value = true
  try {
    await workspace.deleteLayout(props.spaceCode, spec.value.screen, name)
  } finally {
    saving.value = false
  }
  // Back to the screen's own declaration rather than to another screen: which
  // one would we pick? Only when the deleted one is what is open.
  if (layout.value === name) openLayout('')
  else await load()
}

// Hiding is not deleting, and the difference matters: the view stays where it
// is for everybody else. If it is the one open, the screen goes back to its own
// declaration — staying in a view you just took out of your menu reads as a
// button that did nothing.
const hideLayout = async (name) => {
  saving.value = true
  try {
    await workspace.hideLayout(props.spaceCode, spec.value.screen, name)
  } finally {
    saving.value = false
  }
  if (layout.value === name) openLayout('')
  else await load()
}

const showLayouts = () =>
  withView(() => workspace.showLayouts(props.spaceCode, spec.value.screen))

const changed = async () => {
  dirty.value = true
  await loadRows()
}

// --- the list follows the site ----------------------------------------------
//
// Frappe publishes `list_update` for every document that changes, so a list
// left open on a second screen stops being a photograph of when it was opened.
//
// Coalesced, and deliberately: a bulk import or a background job can publish
// hundreds of these in a second, and one refetch per event is a list that
// spends its afternoon reloading. A short wait after the last one is what a
// person experiences as "it just updated".
let pending = null
let watching = null

const follow = (doctype) => {
  if (watching === doctype) return
  if (unfollow) unfollow()
  unfollow = null
  watching = doctype
  if (!doctype) return
  unfollow = onDoctypeChange(doctype, () => {
    // Not while something is unsaved: refetching would replace the rows under
    // a filter somebody is still choosing, and the Save button would then be
    // offering to save a screen they are no longer looking at.
    if (dirty.value) return
    clearTimeout(pending)
    pending = setTimeout(() => loadRows(), 400)
  })
}

let unfollow = null

onBeforeUnmount(() => {
  clearTimeout(pending)
  if (unfollow) unfollow()
})

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

// A record is in the URL, so it is a link somebody can send and a place a
// reload comes back to. What is *not* in the URL is a record that does not
// exist yet: there is nothing to link to, and a stale "new" in a bookmark
// would open an empty form nobody asked for.
const open = (row) => {
  router.push({ query: { ...route.query, record: row.name } })
}

const create = () => {
  preset.value = {}
  showCreate.value = true
}

// New, from somewhere that already knows part of the answer. A board's column
// header is the one today: pressing New inside "In Progress" means a record
// that is in progress, and making the person pick the status they just pressed
// is the kind of small stupidity that makes a board not worth using.
const newWith = (values) => {
  preset.value = values || {}
  showCreate.value = true
}

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

// The record's id changed, so the URL is now pointing at something that no
// longer exists. Replaced rather than pushed: the old id is not a place to go
// back to, and leaving it in the history is leaving a 404 in it.
const recordRenamed = async (name) => {
  if (!name) return
  await router.replace({ query: { ...route.query, record: name } })
  await loadRows()
}

// A record that was just made is a record you want to be in — so the dialog
// closes onto it rather than onto the list, which would leave the person
// hunting for the row they created.
const created = async (name) => {
  await loadRows()
  if (name) router.push({ query: { ...route.query, record: name } })
}

// Somebody else saved it while this was open, and the reader asked for their
// version. The same re-read a save does, without the save.
const reloadRecord = async () => {
  const name = editing.value?.name
  if (!name) return
  editing.value = null
  await openRecord(name)
  await loadRows()
}

// Saving from the pane refreshes the list under it — a title or a status that
// changed is a row that now reads differently — and re-reads the record, so
// what the pane shows is what the server has rather than what was typed.
const recordSaved = async () => {
  await loadRows()
  const name = editing.value?.name
  if (!name) return
  editing.value = null
  await openRecord(name)
}

// Opening it is a fetch rather than a read of the row: the list carries the
// columns somebody chose to see, and the record shows the doctype's whole
// field list. Seeding the form from the row left every unlisted field blank on
// a record that has a value for it.
const openRecord = async (name) => {
  if (!name) {
    editing.value = null
    return
  }
  if (editing.value && editing.value.name === name) return
  const found = await workspace.screenRecord(props.spaceCode, spec.value?.screen || '', name)
  if (!found?.name) {
    // A link to something that is gone, or that this screen does not list.
    // Drop it from the URL rather than leaving a pane that never opens.
    closeRecord()
    return
  }
  editing.value = found
}

const closeRecord = () => {
  editing.value = null
  if (!route.query.record) return
  const query = { ...route.query }
  delete query.record
  router.replace({ query })
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
    // What the rows actually came back grouped by, which is not always what
    // the picker says: pressing Done sets the local answer immediately, and
    // the list would group the rows it still has — in the old order — into
    // headings that repeat, for as long as the request takes. The server sorts
    // by the group column, so the heading appears when the rows sorted for it
    // do.
    groupedBy.value = page?.group_by || ''
    // Same reason as the grouping above: the board the rows were fetched for.
    fetchedBoard.value = page?.board || null
    fetchedCards.value = page?.cards || null
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

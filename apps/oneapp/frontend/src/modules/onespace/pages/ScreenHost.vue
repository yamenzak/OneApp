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
  <div class="flex h-full min-h-0 gap-2">
   <!--
     `v-show` and not `v-if`: on a showcase screen the record takes the whole
     area and the list goes away, but it goes away the way a covered thing does
     — closing the record comes back to the same rows, the same scroll position
     and the same unsaved filter, rather than to a screen that fetches itself
     again.
   -->
   <!--
     The list's panel. The shell draws no frame on this route (`meta.bare`), so
     this is the frame — and when a record opens beside it, the two are two
     panels with the ground between them rather than one panel split down the
     middle by a rule.
   -->
   <div v-show="!asPage" class="flex min-w-0 flex-1 flex-col rounded-6 bg-surface-base p-5">
    <div v-if="loading" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!space"
      icon="lucide-circle-help"
      :title="__('This space is not open to you')"
      :description="__('It is not part of your workspace, or nobody has given you access to it. An admin can change that.')"
    />

    <!--
      A screen the space wrote itself. Nothing else on the screen applies — and it
      gets its own scroll, because the pane does not scroll and a component we
      did not write cannot be assumed to fit.
    -->
    <div v-else-if="custom" class="min-h-0 flex-1 overflow-y-auto">
      <component :is="custom" :space-code="spaceCode" :screen="spec.screen" />
    </div>

    <Alert v-else-if="specError" theme="red" :title="__('This screen did not open')">
      <template #description>{{ specError }}</template>
    </Alert>

    <!--
      An entitlement with no interface is a real thing to be: it still grants
      its roles and doctypes, and something else may be using them.
    -->
    <EmptyState
      v-else-if="!spec?.screens?.length"
      icon="lucide-hammer"
      :title="__('Nothing to show yet')"
      :description="__('{0} is part of your workspace but has no screens in it yet.', [space.space_label])"
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
        <!--
          First in the row, because it is the first thing people reach for: the
          boxes beside it ask one field a question and this asks all of them.
          Narrow on a phone rather than hidden — a list you cannot search on a
          phone is the one place a search box earns its width most.
        -->
        <ListSearch v-model="search" @changed="changed" />
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
            :label="quickExpanded ? __('Fewer filters') : __('More filters')"
            :tooltip="quickExpanded ? __('Fewer filters') : __('More filters')"
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
            :columns="[...(spec.all_columns || []), ...(spec.child_columns || [])]"
            :space-code="spaceCode"
            :screen="spec.screen"
            @changed="onPanelFilters"
          />
          <!--
            How many of each, beside the control that narrows: Frappe puts this
            in its list sidebar and this product's sidebar is the space's own
            navigation, so it is a menu here. Clicking a value adds the filter
            the sidebar's link would have applied.
          -->
          <TallyMenu
            :columns="spec.all_columns || []"
            :status-field="spec.status_field || ''"
            :space-code="spaceCode"
            :screen="spec.screen"
            :layout="spec.layout || ''"
            :overrides="payload()"
            @narrow="narrowTo"
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
            :label="__('Only my favourites')"
            :tooltip="__('Only my favourites')"
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

      <Alert v-else-if="rowsError" theme="red" :title="__('This list did not load')">
        <template #description>{{ rowsError }}</template>
      </Alert>

      <!--
        The way back out lives here, because the header it would otherwise live
        in does not exist when there are no rows — and "only my favourites"
        with nothing liked is exactly when you need the button that turns it
        off again.
      -->
      <!--
        Every view but the calendar. A month with nothing in it is not an empty
        screen — it is a month, and the grid is what you move through to reach
        one that has something in it. Replacing it with "No events yet" takes
        away the only control that would get you back, which is what it did:
        one click into last month and the calendar was gone.
      -->
      <EmptyState
        v-else-if="!rows.length && spec.view_type !== 'calendar'"
        icon="lucide-inbox"
        :title="favourites ? __('Nothing here yet') : __('No {0} yet', [spec.screen_label.toLowerCase()])"
        :description="emptyBecause"
      >
        <template #action>
          <Button
            v-if="favourites"
            icon-left="lucide-heart-off"
            :label="__('Show everything')"
            @click="toggleFavourites"
          />
          <Button
            v-else-if="quickFilters.length || panelFilters.length"
            icon-left="lucide-filter-x"
            :label="__('Clear the filters')"
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
            :open-record="shownRecord?.name || ''"
            :board="fetchedBoard || spec.board || {}"
            :cards="fetchedCards || spec.cards || {}"
            :calendar="fetchedCalendar || spec.calendar || {}"
            :gantt="spec.gantt || {}"
            :tree="spec.tree || {}"
            :place="spec.place || {}"
            :totals="totals"
            :group-totals="groupTotals"
            :space-code="spaceCode"
            :layout="spec.layout || ''"
            :overrides="dashboardAsked"
            @open="open"
            @like="like"
            @sort="sortBy"
            @resize="resizeColumn"
            @favourites="toggleFavourites"
            @change="writeField"
            @changed="cardsChanged"
            @quick="quickCreate"
            @new="newWith"
            @range="showDays"
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
            :exporting="exporting"
            @columns="openSettings"
            @export="exportRows()"
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
            v-if="spec.can_write"
            icon-left="lucide-pencil"
            :label="__('Edit')"
            @click="bulkEditing = true"
          />
          <Button
            v-if="spec.can_write"
            icon-left="lucide-user-plus"
            :label="__('Assign')"
            @click="bulkAssigning = true"
          />
          <!--
            The desk's bulk submit and cancel. Only where the doctype has a
            docstatus at all — a screen over a Note draws neither — and only
            where this person may write: a submit that comes back refused forty
            times is a button that should not have been there.

            Cancel asks first, and it is the only one that does: cancelling
            unwrites a ledger, and forty of them is forty ledgers.
          -->
          <template v-if="submittable && spec.can_write">
            <Button
              icon-left="lucide-check"
              :label="__('Submit')"
              :loading="bulking"
              @click="bulkSubmit"
            />
            <Button
              theme="red"
              variant="subtle"
              icon-left="lucide-undo-2"
              :label="__('Cancel')"
              :loading="bulking"
              @click="confirmBulkCancel = true"
            />
          </template>
          <Button
            v-if="spec.can_print"
            icon-left="lucide-printer"
            :label="__('Print')"
            @click="printSelected"
          />
          <Button
            icon-left="lucide-download"
            :label="__('Export')"
            :loading="exporting"
            @click="exportRows(selection)"
          />
          <Button
            v-if="spec.can_delete"
            theme="red"
            icon-left="lucide-trash-2"
            :label="__('Delete {0}', [selection.length])"
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
    <!-- One change to a whole selection, and the people to give it to. Both
         are dialogs rather than menu items: a bulk change has no undo and no
         per-record confirmation, so it says the number before it happens. -->
    <BulkEditDialog
      v-if="spec?.doctype"
      v-model="bulkEditing"
      :columns="spec.all_columns || []"
      :count="selection.length"
      :space-code="spaceCode"
      :screen="spec.screen"
      :states="spec.states || []"
      :working="bulking"
      @apply="bulkSet"
    />
    <BulkAssignDialog
      v-if="spec?.doctype"
      v-model="bulkAssigning"
      :count="selection.length"
      :space-code="spaceCode"
      :screen="spec.screen"
      :working="bulking"
      @apply="bulkAssign"
    />

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

  <!-- Cancelling unwrites what submitting wrote, and forty of them is forty
       ledgers. The one other bulk operation that asks. -->
  <Dialog
    v-model="confirmBulkCancel"
    :title="selection.length === 1
      ? __('Cancel this record?')
      : __('Cancel {0} records?', [selection.length])"
  >
    <p class="text-p-base text-ink-gray-7">
      {{ __('Cancelling unwinds what submitting wrote. Anything that will not cancel is named.') }}
    </p>
    <template #actions>
      <Button
        theme="red"
        variant="solid"
        :loading="bulking"
        :label="selection.length === 1 ? __('Cancel it') : __('Cancel them')"
        @click="bulkCancel"
      />
    </template>
  </Dialog>

  <!-- Deleting is the one thing on this screen that does not come back, so it
       asks — and says how many, because a selection is easy to lose track of. -->
  <Dialog
    v-model="confirmDelete"
    :title="selection.length === 1
      ? __('Delete this record?')
      : __('Delete {0} records?', [selection.length])"
  >
    <p class="text-p-base text-ink-gray-7">
      {{ __('This cannot be undone. Anything still linked to elsewhere is kept, and named.') }}
    </p>
    <template #actions>
      <Button
        theme="red"
        variant="solid"
        :loading="deleting"
        :label="__('Delete')"
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
    :calendar="fetchedCalendar || spec.calendar || {}"
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
import EmptyState from '@/shared/components/EmptyState.vue'
import ScreenHeader from '@/modules/onespace/components/screen/views/ScreenHeader.vue'
import CreateDialog from '@/modules/onespace/components/screen/record/CreateDialog.vue'
import RecordPane from '@/modules/onespace/components/screen/record/RecordPane.vue'
import RecordView from '@/modules/onespace/components/screen/record/RecordView.vue'
import RecordDrawer from '@/modules/onespace/components/screen/record/RecordDrawer.vue'
import FilterPanel from '@/modules/onespace/components/screen/views/FilterPanel.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import TallyMenu from '@/modules/onespace/components/screen/views/TallyMenu.vue'
import QuickFilters from '@/modules/onespace/components/screen/views/QuickFilters.vue'
import CardSettings from '@/modules/onespace/components/screen/views/CardSettings.vue'
import ColumnPicker from '@/modules/onespace/components/screen/views/ColumnPicker.vue'
import ListFooter from '@/modules/onespace/components/screen/bodies/ListFooter.vue'
import SelectionBar from '@/modules/onespace/components/screen/bodies/SelectionBar.vue'
import ScreenActions from '@/modules/onespace/components/screen/views/ScreenActions.vue'
import BulkEditDialog from '@/modules/onespace/components/screen/views/BulkEditDialog.vue'
import BulkAssignDialog from '@/modules/onespace/components/screen/views/BulkAssignDialog.vue'
import { useBulkActions } from '@/shared/composables/useBulkActions'
import { useCreating } from '@/shared/composables/useCreating'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { useListFollow } from '@/shared/composables/useListFollow'
import { usePeek } from '@/shared/composables/usePeek'
import { useRecordSurface } from '@/shared/composables/useRecordSurface'
import { useRows } from '@/shared/composables/useRows'
import { useRowWrites } from '@/shared/composables/useRowWrites'
import { useSavedViews } from '@/shared/composables/useSavedViews'
import { useScreenAsked } from '@/shared/composables/useScreenAsked'
import { useScreenLayout } from '@/shared/composables/useScreenLayout'
import { useSorting } from '@/shared/composables/useSorting'
import { session } from '@/modules/onespace/lib/shell/session'
import { workspace } from '@/shared/lib/workspace'
import { CARD_VIEW_TYPES, bodyFor } from '@/modules/onespace/lib/screen/viewTypes'
import { applyTheme, clearTheme } from '@/modules/onespace/lib/shell/theme'
import { DRAWER, PAGE, PANE } from '@/modules/onespace/lib/screen/surfaces'
import { screenComponent } from '@/modules/onespace/screens'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

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
const loading = ref(false)
// Why the screen would not resolve at all — a different failure from a list
// that would not load, and the one that used to read as "no screens".
const specError = ref('')
const showColumns = ref(false)
const showCards = ref(false)

/**
 * The days a calendar has on screen, and the one thing that refetches without
 * anything having been changed.
 *
 * Not in the payload: that is what a saved view is made of, and a view carrying
 * "March" in its filters is a view that shows nothing in April. Nothing else
 * reads it — every other body draws the page it was given.
 */
const days = ref(null)

const space = computed(() =>
  (session.spaces || []).find((one) => one.space_code === props.spaceCode),
)

// Which way this screen is being looked at, from the URL. Empty means the
// screen's own first type, which is what the server falls back to — so a link
// without one is a link to the default rather than to nothing.
const viewType = computed(() => route.query.type || '')

// Which body draws this screen. Resolved from the type the server settled on,
// so an unknown or unbuilt one has already fallen back to the list.
const body = computed(() => bodyFor(spec.value?.view_type))

const custom = computed(() => {
  const name = spec.value?.component
  return name ? screenComponent(name) : null
})

// The list's own chrome, kept out of the template so the token audit reads it:
// one hidden in a string the audit cannot see is how `bg-surface-white`
// rendered a transparent column for a week. `rounded-6` is the panel radius.
const SURFACE =
  'flex min-h-0 flex-1 flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base'

// Making a record — `composables/useCreating.js`. The reloads are thunks
// throughout this file: the rows and the screen are resolved further down.
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

// A record opened from inside another one — `composables/usePeek.js`.
const {
  peeked, peekSpec,
  loadPeek, closePeek, peekSaved, expandPeek, peekRenamed,
} = usePeek({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  reloadList: () => loadRows(),
})

// What the reader has asked of this screen — `composables/useScreenAsked.js`.
const {
  quickFilters, panelFilters, search, order, chosenColumns, favourites, groupBy,
  dirty,
  payload, dashboardAsked, askedOfRows, seedFrom, carry, changed,
  onQuickFilters, onPanelFilters, narrowTo, onColumns, clearAllFilters,
  onGroupBy, toggleFavourites, cardsChanged,
} = useScreenAsked({
  spec,
  pageLength: () => pageLength.value,
  reloadRows: () => loadRows(),
  reload: () => load(),
})

/**
 * A column dragged to a new width.
 *
 * Through `onColumns`, the same path the picker's width box takes, rather
 * than a second one: the widths reach the table by being sent up and coming
 * back on the next resolve, so a resize that only changed local state would
 * snap back the first time anything else reloaded.
 */
const resizeColumn = ({ key, width }) =>
  onColumns(
    chosenColumns.value.map((one) =>
      one.fieldname === key ? { ...one, width } : one,
    ),
  )

// The records this screen lists — `composables/useRows.js`.
const {
  rows, columns, selection, total, hasMore, rowsLoading, loadingMore,
  rowsError, pageLength, groupedBy, fetchedBoard, fetchedCards, fetchedCalendar,
  totals, groupTotals,
  loadRows, loadMore, setPageLength,
} = useRows({
  spaceCode: props.spaceCode,
  spec,
  payload: () => payload(),
  range: () => days.value,
  onChange: () => changed(),
})

// Everything done to the ticked rows — `composables/useBulkActions.js`.
const {
  bulkEditing, bulkAssigning, bulking, confirmBulkCancel, confirmDelete,
  deleting, exporting, submittable,
  bulkSet, bulkAssign, bulkSubmit, bulkCancel, printSelected, removeSelected,
  exportRows,
} = useBulkActions({
  spaceCode: props.spaceCode,
  spec,
  selection,
  payload,
  reloadRows: () => loadRows(),
})

// The three writes a body makes — `composables/useRowWrites.js`.
const { writeField, quickCreate, like } = useRowWrites({
  spaceCode: props.spaceCode,
  spec,
  favourites,
  reloadRows: () => loadRows(),
})

// Keeping or discarding an unsaved change — `composables/useScreenLayout.js`.
const {
  saving, resetting, saveLabel, discardLabel,
  saveLayout, discardChanges,
} = useScreenLayout({
  spaceCode: props.spaceCode,
  spec,
  dirty,
  payload,
  reload: () => load(),
})

// A screen is a named layout — filters, sort and columns saved together, the
// shape Frappe's own `List Filter` doctype settles on. Which one is open lives
// in the URL, so a screen is a link somebody can send.
//
// Kept whole as well as destructured: `ScreenHeader` takes the object, because
// the switcher's menu is exactly this composable and forwarding its nine verbs
// one event at a time says nothing that `:views="views"` does not.
const views = useSavedViews({
  spaceCode: props.spaceCode,
  spec,
  route,
  router,
  saving,
  dirty,
  payload: () => payload(),
  reload: (into) => load(into),
})
const { layout } = views

// The order the list is in — `composables/useSorting.js`.
const { sortBy } = useSorting({ order, spec, onChange: () => changed() })

// Where the reader is, as the header draws it — `composables/useCrumbs.js`.
const { viewLabel, crumbs, recordCrumb, statusValue, docState } = useCrumbs({
  spaceCode: props.spaceCode,
  spec,
  space,
  shownRecord,
  viewType,
})

// The list follows the site — `composables/useListFollow.js`.
const { follow } = useListFollow({ paused: dirty, reload: () => loadRows() })

// Whether the body is showing the activity column, which is where the heart
// lives when it is: above the hearts on the rows, which is the only place the
// control and the thing it filters line up. When it is not, the heart comes to
// the toolbar instead. Never both, never neither.
const META_FIELD = '__activity'
const metaColumn = computed(() =>
  (columns.value || []).some((column) => column.fieldname === META_FIELD),
)

const counted = computed(() =>
  hasMore.value ? `${rows.value.length}+` : String(rows.value.length),
)

const emptyBecause = computed(() => {
  if (favourites.value) return __('Nothing you have liked is on this screen.')
  if (quickFilters.value.length || panelFilters.value.length) {
    return __('Nothing matches the filters. Clear one to widen the list.')
  }
  return spec.value?.can_create
    ? __('Nothing here so far. New starts the first one.')
    : __('Nothing here so far.')
})

// One gear, two dialogs. Which one is the body's question, not the footer's:
// a card view has no column widths and a list has no cards.
const openSettings = () => {
  if (CARD_VIEW_TYPES.includes(spec.value?.view_type)) showCards.value = true
  else showColumns.value = true
}

const showDays = (asked) => {
  if (days.value?.since === asked?.since && days.value?.until === asked?.until) return
  days.value = asked
  loadRows()
}

// What the last render was actually of — the screen, and the way of looking the
// server settled on, which is not always the one the URL asked for. Only a
// change of view type carries anything: another screen is another set of
// records and has nothing to carry.
const drawnAs = ref({ screen: '', type: '' })

const load = async (openWith, carried = null) => {
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
    seedFrom(spec.value)
    pageLength.value = spec.value?.page_length || 100
    drawnAs.value = {
      screen: spec.value?.screen || '',
      type: spec.value?.view_type || '',
    }
    if (carried) carry(carried)
    follow(spec.value?.doctype || '')
    await loadRows()
  } catch (err) {
    // A screen that will not resolve is not a screen with nothing on it. The
    // spec is fetched silently, so a refused one used to leave `spec` null and
    // fall through to "this space has no screens" — which sent us looking at
    // the manifest for an hour while the real answer, a permission the fixture
    // had not written, was in the response body all along.
    spec.value = null
    specError.value = errorText(err)
  } finally {
    loading.value = false
  }
}

/**
 * The space's own look, on the document while this space is open.
 *
 * Read from the session's list of spaces rather than from `spec`: the session
 * is already in hand when the route resolves, so a themed space arrives themed
 * instead of painting one light frame and then turning dark. Taken off on the
 * way out — a space's personality is that space's.
 */
watch(
  () => props.spaceCode,
  (code) => applyTheme(session.spaces.find((one) => one.space_code === code)?.theme),
  { immediate: true },
)

onBeforeUnmount(clearTheme)

// Re-resolved on every screen change: the columns, the filters and what this
// user may do are all per screen, not per space.
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
// parameter out of the URL: a link straight to a workspace opened empty.
watch([() => route.query.record, () => spec.value?.screen], ([name, screen]) => {
  if (screen && !spec.value?.component) openRecord(name || '')
})
</script>

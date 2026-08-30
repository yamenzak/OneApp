<template>
  <PageHeader>
    <div class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs" />
      <ViewSwitcher
        v-if="spec?.doctype"
        :layouts="spec.layouts || []"
        :active="spec.layout || ''"
        :screen-label="spec.view_label"
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
      v-else-if="!app"
      icon="lucide-circle-help"
      title="App not available"
      description="This app is not enabled for your workspace, or you do not have access to it."
    />

    <!--
      A screen the app wrote itself. Nothing else on the view applies — and it
      gets its own scroll, because the pane does not scroll and a component we
      did not write cannot be assumed to fit.
    -->
    <div v-else-if="custom" class="min-h-0 flex-1 overflow-y-auto">
      <component :is="custom" :app-code="appCode" :view="spec.view" />
    </div>

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
      <div class="mb-4 flex shrink-0 flex-col gap-2 sm:flex-row sm:items-start">
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
            @click="toggleFavourites"
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

      <!--
        One surface, with its own horizontal scroller. A view shows the same
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
          <div class="relative flex min-h-0 flex-1 flex-col">
            <!--
              One scroller, both directions. That is the whole trick: with the
              pane a fixed height, this element's horizontal scrollbar sits at
              its own bottom edge — on screen, above the footer — instead of at
              the bottom of a table you have to scroll down to reach. Sharing
              one container with the rows is also what keeps the sticky header
              aligned: a separate header would sit outside the vertical
              scrollbar's gutter and be a scrollbar's width out of true.
            -->
            <div
              ref="scroller"
              class="min-h-0 flex-1 overflow-auto overscroll-x-contain"
              @scroll.passive="measureEdges"
            >
              <List
                v-model:selection="selection"
                :columns="tracks"
                :row-height="52"
                selectable
                class="w-max min-w-full list-row-px-3 pb-1"
                :class="CHROME"
                divider="full"
              >
                <ListHeader class="sticky top-0 z-20">
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
                  How many, then favourites. The heart is last and
                  the cell is end-aligned, so it lands on exactly the x every row's
                  heart lands on — the header and the rows carry the same inset, so
                  flush-right in both is the same pixel. Packed from the start it
                  was not, which is what made the column of hearts look crooked.

                  The count goes in `#prefix` rather than the default slot because
                  `ListHeaderCell` wraps its default in a `truncate` span: `mr-auto`
                  inside that does nothing, since the span is not the flex row.
                -->
                  <ListHeaderCell
                    v-if="metaColumn"
                    class="justify-end"
                    :class="metaColumn.pin && PINNED"
                    :style="stickyStyle(metaColumn)"
                  >
                    <template #prefix>
                      <span class="whitespace-nowrap text-p-xs text-ink-gray-5">{{ counted }}</span>
                    </template>
                    <template #suffix>
                      <Button
                        icon="lucide-heart"
                        :variant="favourites ? 'subtle' : 'ghost'"
                        :theme="favourites ? 'red' : 'gray'"
                        label="Only my favourites"
                        @click="toggleFavourites"
                      />
                    </template>
                  </ListHeaderCell>
                </ListHeader>

                <!--
                One group per run of rows sharing a value. The server sorts by the
                group column first, so a run is a group — which is why this is
                chunking rather than bucketing, and why a group never appears twice.
              -->
                <template v-if="groups">
                  <ListGroup v-for="group in groups" :key="group.label" :label="group.label" sticky>
                    <ListRows :items="group.rows" row-key="name" v-slot="{ item: row, value }">
                      <ListRow :value="value">
                        <ListCell
                          v-for="c in visible"
                          :key="c.key"
                          :class="c.pin && PINNED"
                          :style="stickyStyle(c)"
                        >
                          <TitleCell
                            v-if="c.cell === 'title'"
                            :row="row"
                            :title-field="spec.title_field"
                            :image-field="spec.image_field"
                            @open="open(row)"
                          />
                          <RowMeta
                            v-else-if="c.cell === 'meta'"
                            :meta="row._meta || {}"
                            @like="like(row)"
                          />
                          <FieldCell
                            v-else
                            :column="c.column"
                            :value="row[c.column.fieldname]"
                            :states="spec.states"
                          />
                        </ListCell>
                      </ListRow>
                    </ListRows>
                  </ListGroup>
                </template>

                <!--
                  Windowed past a few hundred. Load more appends, so a list someone
                  keeps loading reaches thousands of rows, and thousands of rows
                  each carrying an avatar, badges and two buttons is a slow page.
                  Below the threshold the plain path is simpler and behaves better
                  with a keyboard.
                -->
                <ListRows
                  v-else
                  :items="rows"
                  row-key="name"
                  :virtual="windowed"
                  v-slot="{ item: row, value }"
                >
                  <ListRow :value="value">
                    <ListCell
                      v-for="c in visible"
                      :key="c.key"
                      :class="c.pin && PINNED"
                      :style="stickyStyle(c)"
                    >
                      <TitleCell
                        v-if="c.cell === 'title'"
                        :row="row"
                        :title-field="spec.title_field"
                        :image-field="spec.image_field"
                        @open="open(row)"
                      />
                      <RowMeta
                        v-else-if="c.cell === 'meta'"
                        :meta="row._meta || {}"
                        @like="like(row)"
                      />
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
            </div>

            <!--
              A table wide enough to scroll has to say so. The scrollbar is on
              screen now, but an overlay scrollbar fades and a full-bleed column
              at the edge reads as the end of the table — so the edge with more
              beyond it carries a shadow, and it goes away when there is not.
            -->
            <div v-if="edges.left" aria-hidden="true" :class="[EDGE, 'left-0', EDGE_LEFT]" />
            <div v-if="edges.right" aria-hidden="true" :class="[EDGE, 'right-0', EDGE_RIGHT]" />
          </div>

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
    :app-code="appCode"
    :view="spec.view"
    @saved="loadRows"
  />
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  ListGroup,
  ListCell,
  Icon,
  Dialog,
} from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import FieldCell from '../components/app/FieldCell.vue'
import TitleCell from '../components/app/TitleCell.vue'
import RowMeta from '../components/app/RowMeta.vue'
import RecordDialog from '../components/app/RecordDialog.vue'
import FilterPanel from '../components/app/FilterPanel.vue'
import QuickFilters from '../components/app/QuickFilters.vue'
import ColumnPicker from '../components/app/ColumnPicker.vue'
import ListFooter from '../components/app/ListFooter.vue'
import SelectionBar from '../components/app/SelectionBar.vue'
import ViewSwitcher from '../components/app/ViewSwitcher.vue'
import { session } from '../lib/session'
import { workspace } from '../lib/workspace'
import { notifyError, notifySuccess } from '../lib/notify'
import { appComponent } from '../apps'

const props = defineProps({ appCode: { type: String, required: true } })
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
const scroller = ref(null)
// Whether there is more table beyond each edge. Both false on a list that fits.
const edges = ref({ left: false, right: false })
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

  // No screen-size branching, deliberately. A view is a saved answer to "what
  // do I look at", and a phone that silently drops half of it is answering a
  // different question — so the phone gets the same columns and scrolls. Frappe
  // CRM does the same, and it is only possible because the columns are the
  // reader's to choose.
  return chosen.map((column) => ({
    key: column.fieldname,
    header: column.label,
    track: `${column.width}px`,
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

// Every declared column, and its track. There is nothing between the spec and
// the grid any more: `useListColumns` exists to narrow a hand-authored list for
// a phone, and this list is neither hand-authored nor narrowed.
const visible = columnSpec
const tracks = computed(() => visible.value.map((c) => c.track))

// The server's name for the column that is not a field.
const META_FIELD = '__activity'

// A pinned column stops scrolling. Opaque, or the columns sliding under it read
// through it — and the offset is an inline style rather than a class because it
// is a computed pixel value, not a token.
const PINNED = 'sticky z-10 bg-surface-base'

// The list's own chrome, kept out of the template so the token audit reads it:
// a class list in an attribute this long is unreadable, and one hidden in a
// string the audit cannot see is how `bg-surface-white` rendered a transparent
// column for a week.
//
// `rounded-6` is the panel radius — the same one every card on this surface
// uses. See `docs/APPS.md` for the scale.
const SURFACE =
  'flex min-h-0 flex-1 flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base'

// The band behind the column headers, and the reason `ListHeader`'s own rule is
// off: that rule is a grid child inset to the content box, so under a
// full-width fill it stopped short at both ends. The band carries its own
// full-width rule instead.
// The edge affordance: a wash over the column at whichever side has more beyond
// it. Not a border — a border says "the table ends here", which is the opposite
// of what this means.
//
// It has to be legible, which the first version was not: this environment's
// scrollbars are overlay ones, so the horizontal bar is invisible until you are
// already scrolling and this is the *only* thing saying there is more. Above
// the sticky header's z-index too, or it stops at the first row.
const EDGE = 'pointer-events-none absolute inset-y-0 z-30 w-10'
const EDGE_LEFT = 'bg-gradient-to-r from-surface-gray-4 to-transparent opacity-70'
const EDGE_RIGHT = 'bg-gradient-to-l from-surface-gray-4 to-transparent opacity-70'

// How many rows before windowing them is worth the complexity it adds. A
// computed rather than an inline comparison: a `>` inside a template attribute
// ends the tag as far as any regex-shaped parser is concerned, which is how the
// frappe-ui prop guard once read `visible.length` as a prop name.
const VIRTUAL_FROM = 200

const CHROME = [
  '[&_[data-slot=list-header]]:h-9',
  '[&_[data-slot=list-header]]:bg-surface-gray-1',
  '[&_[data-slot=list-header]]:border-b',
  '[&_[data-slot=list-header]]:border-outline-gray-2',
  '[&_[data-slot=list-header-border]]:hidden',
  // A group heading sticks *under* the column header rather than over it —
  // ListGroup pins at `top-0`, which is where the header already is.
  '[&_[data-slot=list-group-header]]:top-9',
].join(' ')

const stickyStyle = (c) => (c.pin ? { [c.pin]: `${c.offset}px` } : undefined)

const sortableColumns = computed(() => visible.value.filter((c) => c.cell !== 'meta'))
const metaColumn = computed(() => visible.value.find((c) => c.cell === 'meta') || null)

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned, which
// is how the frappe-ui prop guard read `visible.length` as a prop name.
const windowed = computed(() => rows.value.length > VIRTUAL_FROM)

// Null when nothing is grouped, so the template can tell "no grouping" from
// "one group".
const groups = computed(() => {
  const field = groupBy.value
  if (!field) return null

  const made = []
  for (const row of rows.value) {
    const value = row[field]
    const label = value === null || value === undefined || value === '' ? '—' : String(value)
    const last = made[made.length - 1]
    if (last && last.label === label) last.rows.push(row)
    else made.push({ label, rows: [row] })
  }
  return made
})

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

// The trail stops at the app, because the switcher beside it is the next
// level: it opens on the screen's own name and every saved view of it, so a
// crumb saying the same word again is one word twice.
const crumbs = computed(() => {
  const trail = [{ label: 'Apps', route: { name: 'Launcher' } }]
  if (app.value) trail.push({ label: app.value.app_label })
  if (!spec.value?.doctype && spec.value?.view_label && spec.value.views?.length > 1) {
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
  group_by: groupBy.value,
  page_length: pageLength.value,
})

// --- the scroller -----------------------------------------------------------

// Read rather than tracked: a scroll position is the DOM's own state, and
// mirroring it into a ref that then has to be kept in step is how the two end
// up disagreeing.
const measureEdges = () => {
  const el = scroller.value
  if (!el) return
  const room = el.scrollWidth - el.clientWidth
  edges.value = {
    left: el.scrollLeft > 1,
    // A pixel of slack: a fractional layout width leaves half a pixel of
    // scrollWidth that is not more table.
    right: room > 1 && el.scrollLeft < room - 1,
  }
}

// --- views ------------------------------------------------------------------
//
// A view is a named layout — filters, sort and columns saved together — which
// is the shape Frappe's own `List Filter` doctype settles on. Which one is open
// lives in the URL, so a view is a link somebody can send.

const layout = computed(() => route.query.layout || '')

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
    const result = await workspace.saveView(props.appCode, spec.value.view, {
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
    workspace.saveView(props.appCode, spec.value.view, {
      ...payload(),
      layout: spec.value.layout,
      label,
      shared,
    }),
  )

const shareLayout = (shared) =>
  withView(() =>
    workspace.saveView(props.appCode, spec.value.view, {
      ...payload(),
      layout: spec.value.layout,
      shared,
    }),
  )

const defaultLayout = () =>
  withView(() => workspace.defaultView(props.appCode, spec.value.view, spec.value.layout))

const deleteLayout = async () => {
  const gone = spec.value.layout
  saving.value = true
  try {
    await workspace.deleteView(props.appCode, spec.value.view, gone)
  } finally {
    saving.value = false
  }
  // Back to the screen's own declaration rather than to another view: which
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
  const result = await workspace.toggleLike(props.appCode, spec.value.view, row.name)
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
    const result = await workspace.removeAppRecords(props.appCode, spec.value.view, [
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
  workspace.appRows(
    props.appCode,
    spec.value.view,
    payload(),
    spec.value.layout || '',
    { start, limit: pageLength.value },
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
    nextTick(measureEdges)
  }
}

// Asked after the rows and never awaited with them: the footer says how many
// are loaded until this answers, and then how many there are.
let counting = 0
const countRows = async () => {
  const asked = ++counting
  total.value = null
  try {
    const answer = await workspace.appRowCount(
      props.appCode,
      spec.value.view,
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
    nextTick(measureEdges)
  }
}

// A page size is part of the view, so changing it is a change to save like any
// other — and it starts the list again rather than truncating what is loaded.
const setPageLength = (size) => {
  if (!size || size === pageLength.value) return
  pageLength.value = size
  changed()
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

const load = async (openWith) => {
  if (!app.value) return
  loading.value = true
  try {
    spec.value = await workspace.appView(
      props.appCode,
      route.query.view || '',
      openWith || layout.value,
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

// The scroll width changes without a scroll: rows arriving, a column resized or
// added, the window narrowed. None of those fire `scroll`, and an edge shadow
// left behind on a table that now fits is a lie about there being more.
//
// A ResizeObserver rather than a watcher and a nextTick. That is what the first
// attempt was, and it measured a table that was not laid out yet — the shadow
// only appeared once something else caused a scroll, so a list that opened too
// wide said nothing at all. An observer fires when the box is real.
const observer = new ResizeObserver(measureEdges)

watch(
  scroller,
  (el) => {
    observer.disconnect()
    if (!el) return
    // Both boxes: the viewport and the content. Only one of them changes when
    // the window narrows, and only the other when a column is widened.
    observer.observe(el)
    if (el.firstElementChild) observer.observe(el.firstElementChild)
    measureEdges()
  },
  { flush: 'post' },
)

// The content's own width changes when rows arrive without the container
// resizing at all — an `auto` track sizing to a longer value.
watch([visible, rows], () => nextTick(measureEdges), { flush: 'post' })

onUnmounted(() => observer.disconnect())

// Re-resolved on every view change: the columns, the filters and what this user
// may do are all per view, not per app.
watch(
  [() => props.appCode, () => route.query.view, () => route.query.layout, () => session.loaded],
  () => load(),
  { immediate: true },
)
</script>

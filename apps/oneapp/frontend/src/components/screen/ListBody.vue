<template>
  <!--
    The list: a fixed-height grid inside the screen's pane.

    One of several bodies a screen can be looked at through — the shell above
    owns everything a body does not: the breadcrumbs, the saved views, the
    filters, the selection bar and the footer. A body owns its own scrolling
    and nothing else, which is what makes a board or a calendar a sibling of
    this file rather than a rewrite of the screen.
  -->
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
        v-model:selection="chosen"
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
            @click="emit('sort', c.column.fieldname)"
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
                tooltip="Only my favourites"
                @click="emit('favourites')"
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
                    @open="emit('open', row)"
                  />
                  <RowMeta
                    v-else-if="c.cell === 'meta'"
                    :meta="row._meta || {}"
                    @like="emit('like', row)"
                  />
                  <FieldCell
                    v-else
                    :column="c.column"
                    :value="row[c.column.fieldname]"
                    :links="row._links || {}"
                    :states="spec.states"
                    :space-code="spec.space"
                    :screen="spec.screen"
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
                @open="emit('open', row)"
              />
              <RowMeta
                v-else-if="c.cell === 'meta'"
                :meta="row._meta || {}"
                @like="emit('like', row)"
              />
              <FieldCell
                v-else
                :column="c.column"
                :value="row[c.column.fieldname]"
                :links="row._links || {}"
                :states="spec.states"
                :space-code="spec.space"
                :screen="spec.screen"
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
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import {
  Button,
  Icon,
  List,
  ListCell,
  ListGroup,
  ListHeader,
  ListHeaderCell,
  ListHeaderCellSort,
  ListRow,
  ListRows,
} from '@/ui'
import FieldCell from './FieldCell.vue'
import TitleCell from './TitleCell.vue'
import RowMeta from './RowMeta.vue'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /** The columns the rows actually came back with, as the picker left them. */
  columns: { type: Array, default: () => [] },
  /** `field asc|desc`, so the header can show which way it is sorted. */
  orderBy: { type: String, default: '' },
  /** Whether the favourites filter is on, for the heart in the header. */
  favourites: { type: Boolean, default: false },
  /** How many rows there are, for the count in the activity header. */
  counted: { type: String, default: '' },
  /** Which column the rows are grouped under, or empty. */
  groupBy: { type: String, default: '' },
})

const emit = defineEmits(['open', 'like', 'sort', 'favourites'])

const selection = defineModel('selection', { type: Array, default: () => [] })
const chosen = selection

const META_FIELD = '__activity'

// A pinned column stops scrolling. Opaque, or the columns sliding under it read
// through it — and the offset is an inline style rather than a class because it
// is a computed pixel value, not a token.
const PINNED = 'sticky z-10 bg-surface-base'

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

// How many rows before windowing them is worth the complexity it adds.
const VIRTUAL_FROM = 200

// The band behind the column headers, and the reason `ListHeader`'s own rule is
// off: that rule is a grid child inset to the content box, so under a
// full-width fill it stopped short at both ends. The band carries its own
// full-width rule instead.
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

const scroller = ref(null)
// Whether there is more table beyond each edge. Both false on a list that fits.
const edges = ref({ left: false, right: false })

// One model for every column. The title field renders with its avatar and id,
// activity renders its own cell, everything else is a value — but all three are
// entries in the same list, so all three can be moved, resized, pinned and
// dropped in the picker.
//
// No screen-size branching, deliberately. A view is a saved answer to "what do
// I look at", and a phone that silently drops half of it is answering a
// different question — so the phone gets the same columns and scrolls. Frappe
// CRM does the same, and it is only possible because the columns are the
// reader's to choose.
// What a row spends on things that are not columns: the checkbox inset the
// List adds for `selectable`, the row padding `list-row-px-3` sets at both
// ends, and the column gap between every pair of tracks. Read off frappe-ui's
// own `style.css` rather than guessed — the first version forgot the gaps and
// left the table four pixels wider than the pane, which is a horizontal
// scrollbar over nothing.
const CHECKBOX = 32
const ROW_PAD = 12 * 2
const COLUMN_GAP = 8

// Three columns in a wide pane is a small table in a pool of white space. The
// leftover width goes to the title, because a name is the thing a wider list
// should show more of — and it goes in as pixels rather than as an `fr` track,
// so the pinning offsets and the edge measurement keep working off one set of
// numbers.
const widened = computed(() => {
  const declared = props.columns || []
  const fixed = declared.reduce((total, c) => total + c.width, 0)
  const gaps = Math.max(declared.length - 1, 0) * COLUMN_GAP
  const slack = paneWidth.value - CHECKBOX - ROW_PAD - gaps - fixed
  if (slack <= 0) return declared

  const title = props.spec?.title_field
  const grows =
    declared.find((c) => c.fieldname === title) || declared.find((c) => !c.pin) || declared[0]
  return declared.map((c) => (c === grows ? { ...c, width: c.width + slack } : c))
})

const visible = computed(() => {
  const titleField = props.spec?.title_field
  const declared = widened.value

  // Where a pinned column starts, in pixels. A left pin sits past everything
  // pinned left before it; a right pin past everything pinned right after it.
  // Fixed widths are what make this computable at all.
  let fromLeft = 0
  const offsets = new Map()
  for (const column of declared) {
    if (column.pin !== 'left') continue
    offsets.set(column.fieldname, fromLeft)
    fromLeft += column.width
  }
  let fromRight = 0
  for (const column of [...declared].reverse()) {
    if (column.pin !== 'right') continue
    offsets.set(column.fieldname, fromRight)
    fromRight += column.width
  }

  return declared.map((column) => ({
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

const tracks = computed(() => visible.value.map((c) => c.track))
const sortableColumns = computed(() => visible.value.filter((c) => c.cell !== 'meta'))
const metaColumn = computed(() => visible.value.find((c) => c.cell === 'meta') || null)

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned, which
// is how the frappe-ui prop guard read `visible.length` as a prop name.
const windowed = computed(() => props.rows.length > VIRTUAL_FROM)

const stickyStyle = (c) => (c.pin ? { [c.pin]: `${c.offset}px` } : undefined)

const sortField = computed(() => (props.orderBy || '').split(' ')[0])
const ascending = computed(() => (props.orderBy || '').split(' ')[1] === 'asc')

const directionFor = (c) => {
  if (c.column.fieldname !== sortField.value) return undefined
  return ascending.value ? 'asc' : 'desc'
}

// Null when nothing is grouped, so the template can tell "no grouping" from
// "one group".
const groups = computed(() => {
  const field = props.groupBy
  if (!field) return null

  const made = []
  for (const row of props.rows) {
    const value = row[field]
    const label = value === null || value === undefined || value === '' ? '—' : String(value)
    const last = made[made.length - 1]
    if (last && last.label === label) last.rows.push(row)
    else made.push({ label, rows: [row] })
  }
  return made
})

// How much room the pane has, which is what decides whether the tracks add up
// to less than it. Measured by the same observer the edges use — there is one
// question here, asked when the box changes.
const paneWidth = ref(0)

// Read rather than tracked: a scroll position is the DOM's own state, and
// mirroring it into a ref that then has to be kept in step is how the two end
// up disagreeing.
const measureEdges = () => {
  const el = scroller.value
  if (!el) return
  paneWidth.value = el.clientWidth
  const room = el.scrollWidth - el.clientWidth
  edges.value = {
    left: el.scrollLeft > 1,
    // A pixel of slack: a fractional layout width leaves half a pixel of
    // scrollWidth that is not more table.
    right: room > 1 && el.scrollLeft < room - 1,
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
watch([visible, () => props.rows], () => nextTick(measureEdges), { flush: 'post' })

onUnmounted(() => observer.disconnect())
</script>

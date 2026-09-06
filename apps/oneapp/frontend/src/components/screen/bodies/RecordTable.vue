<template>
  <!--
    A table of records: tracks, a sticky header, pinned columns, edges that say
    there is more, and windowing past a few hundred rows.

    What it is not is a *list*. It knows nothing about what a cell contains,
    what a row click means, where the rows came from, or whether they can be
    sorted — those are the consumer's, through slots and props. `ListBody` draws
    a screen's records with it; `ChildTable` draws the rows inside one record
    with it. One table means one place to be wrong.
  -->
  <div class="relative flex min-h-0 flex-col" :class="fills ? 'flex-1' : ''">
    <!--
      One scroller, both directions. With the pane a fixed height its horizontal
      scrollbar sits at its own bottom edge instead of at the bottom of a table
      you have to scroll down to reach — and sharing one container with the rows
      is what keeps the sticky header aligned.
    -->
    <!--
      Which axes it scrolls is the height mode, and that is the only difference
      between a table that fills a pane and one that sits in a form.
    -->
    <div
      ref="scroller"
      :class="fills ? 'min-h-0 flex-1 overflow-auto overscroll-x-contain' : 'overflow-x-auto'"
      @scroll.passive="measureEdges"
    >
      <List
        v-model:selection="chosen"
        :columns="tracks"
        :row-height="rowHeight"
        :selectable="selectable"
        :divider="divider"
        :class="[
          shares ? 'w-full' : 'w-max min-w-full',
          rowInset,
          extraClass,
          band ? BAND : '',
        ]"
      >
        <ListHeader :class="sticky ? 'sticky top-0 z-20' : ''">
          <template v-for="c in placed" :key="c.key">
            <!--
              A column the consumer draws itself, whole: the count and the
              favourites heart live in `#prefix` and `#suffix` of their cell,
              which a content slot cannot reach.
            -->
            <slot
              v-if="$slots[`header-${c.key}`]"
              :name="`header-${c.key}`"
              :column="c"
              :pinned="c.pin ? PINNED : ''"
              :style="stickyStyle(c)"
            />

            <!--
              Sorting lives on the headers, the only place a direction can sit
              beside the thing it applies to. frappe-ui ships the cell for it,
              so this wires state to it rather than rebuilding it.
            -->
            <!--
              `aligned` here too, and it was missing: only the plain header cell
              carried it, so every sortable column sat left over right-aligned
              numbers.
            -->
            <ListHeaderCellSort
              v-else-if="c.sortable"
              :direction="directionFor(c)"
              :class="[c.pin && PINNED, aligned(c)]"
              :style="stickyStyle(c)"
              @click="emit('sort', c.key)"
            >
              <template #prefix v-if="c.icon">
                <Icon :name="c.icon" class="size-3.5 text-ink-gray-4" />
              </template>
              {{ c.label }}
            </ListHeaderCellSort>

            <ListHeaderCell
              v-else
              :class="[c.pin && PINNED, aligned(c)]"
              :style="stickyStyle(c)"
            >
              <template #prefix v-if="c.icon">
                <Icon :name="c.icon" class="size-3.5 text-ink-gray-4" />
              </template>
              {{ c.label }}
              <!--
                A required column says so where its label is said. A grid cell has
                no room for one, so without this the only warning is the save
                failing.
              -->
              <template #suffix v-if="c.required">
                <span class="text-ink-red-4" aria-hidden="true">*</span>
              </template>
            </ListHeaderCell>
          </template>
        </ListHeader>

        <!--
          One group per run of rows sharing a value. Whoever sorted the rows put
          the group column first, so a run *is* a group — which is why this
          chunks rather than buckets, and why a group never appears twice.
        -->
        <template v-if="groups">
          <ListGroup v-for="group in groups" :key="group.label" :label="group.label" sticky>
            <!--
              What the group adds up to. On the heading rather than a row of its
              own: a subtotal under a run of rows reads as another row.
            -->
            <template v-if="group.note" #header>
              <span class="flex w-full items-baseline gap-2 pe-2">
                <span>{{ group.label }}</span>
                <span class="ms-auto tabular-nums text-ink-gray-6">{{ group.note }}</span>
              </span>
            </template>
            <ListRows
              :items="group.rows"
              :row-key="rowKey"
              v-slot="{ item: row, value, index }"
            >
              <ListRow :value="value" v-bind="rowProps(row, index)">
                <ListCell
                  v-for="c in placed"
                  :key="c.key"
                  :class="[c.pin && PINNED, aligned(c)]"
                  :style="stickyStyle(c)"
                  @click="clicked(row, index, $event)"
                >
                  <slot name="cell" :column="c" :row="row" :index="index" />
                </ListCell>
              </ListRow>
            </ListRows>
          </ListGroup>
        </template>

        <!--
          Windowed past a few hundred. Thousands of rows each carrying an
          avatar, badges and two buttons is a slow page; below the threshold the
          plain path behaves better with a keyboard.
        -->
        <ListRows
          v-else
          :items="rows"
          :row-key="rowKey"
          :virtual="windowed"
          v-slot="{ item: row, value, index }"
        >
          <ListRow :value="value" v-bind="rowProps(row, index)">
            <ListCell
              v-for="c in placed"
              :key="c.key"
              :class="[c.pin && PINNED, aligned(c)]"
              :style="stickyStyle(c)"
              @click="clicked(row, index, $event)"
            >
              <slot name="cell" :column="c" :row="row" :index="index" />
            </ListCell>
          </ListRow>
        </ListRows>

        <!--
          A row of totals, stuck to the bottom edge. A `ListHeader` rather than a
          `ListRow`, which is what it structurally is: the same tracks, the same
          pinning arithmetic, and none of a row's selection or click behaviour.
        -->
        <!--
          The select-all is hidden rather than absent: `ListHeader` draws one
          whenever the list is selectable and offers no way to say otherwise.
          `invisible` rather than `hidden` so the cell keeps its width.

          Mounted with the table rather than with the numbers: `ListHeader` sets
          the flag that puts the list into table semantics and clears it on
          unmount, so a totals row that came and went would take `role="table"`
          with it.
        -->
        <ListHeader
          v-if="$slots.total"
          class="sticky bottom-0 z-20 border-t border-outline-gray-2
                 [&_[data-slot=list-header-checkbox]]:invisible"
        >
          <ListHeaderCell
            v-for="c in placed"
            :key="c.key"
            :class="[c.pin && PINNED, aligned(c)]"
            :style="stickyStyle(c)"
          >
            <slot name="total" :column="c" />
          </ListHeaderCell>
        </ListHeader>
      </List>
    </div>

    <!--
      A table wide enough to scroll has to say so: an overlay scrollbar fades and
      a full-bleed column at the edge reads as the end of the table.
    -->
    <div v-if="edges.left" aria-hidden="true" :class="[EDGE, 'left-0']" />
    <div v-if="edges.right" aria-hidden="true" :class="[EDGE, 'right-0']" />
  </div>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import {
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

const props = defineProps({
  /**
   * The columns, in order. Each is
   * `{ key, label, icon?, track, width?, pin?, align?, required?, sortable? }`.
   *
   * `track` is a CSS grid track; `width` is the same number as pixels and is
   * only needed for pinning and for `fill`, both of which are arithmetic over
   * widths.
   */
  columns: { type: Array, required: true },
  rows: { type: Array, default: () => [] },
  /** `'name'`, or a function — see frappe-ui's `ListRows.rowKey`. */
  rowKey: { type: [String, Function], default: 'name' },
  rowHeight: { type: Number, default: 52 },
  selectable: { type: Boolean, default: false },
  divider: { type: String, default: 'full' },
  /** `field asc|desc`, so a sortable header can show which way it is sorted. */
  orderBy: { type: String, default: '' },
  /** `[{ label, rows, note }]`, or null when nothing is grouped. */
  groups: { type: Array, default: null },
  /** Rows past which they are windowed. 0 never windows them. */
  virtualFrom: { type: Number, default: 0 },
  /**
   * The column that takes whatever width is left over, by key. The slack goes
   * in as pixels rather than as an `fr` track so the pinning offsets and the
   * edge measurement keep working off one set of numbers — which is why this
   * only applies where every column has a `width`.
   */
  fill: { type: String, default: '' },
  /** Attributes and listeners to bind on each row — the drag handlers. */
  rowProps: { type: Function, default: () => () => ({}) },
  /** The header's own band. A table inside a panel already has a border. */
  band: { type: Boolean, default: false },
  sticky: { type: Boolean, default: false },
  /** Anything else for the grid element. Not the row inset — see `rowInset`. */
  extraClass: { type: String, default: '' },
  /** Whether it fills the height it is given, or is as tall as its rows. */
  fills: { type: Boolean, default: false },
})

const emit = defineEmits(['sort', 'row-click'])

const chosen = defineModel('selection', { type: Array, default: () => [] })

// A pinned column stops scrolling. Opaque, or the columns sliding under it read
// through it; the offset is an inline style because it is a computed pixel
// value, not a token.
/**
 * The row inset, decided here rather than handed in.
 *
 * `list-row-px-3` sets frappe-ui's public `--list-row-padding-x`, which the
 * *header* reads. The rows read a private one the library sets only on
 * `[data-interactive]` rows. So the class is right for a selectable table and
 * wrong for a static one, where it insets the header and leaves the rows flush
 * under it. A static table pads the grid instead, which moves both together.
 */
const rowInset = computed(() => (props.selectable ? 'list-row-px-3' : 'px-3'))

// Computed rather than a ternary in the binding: `test_every_class_emits_css`
// reads the string literals out of a `:class`, and `align === 'end' ? …`
// offered it `end` as a class name.
const RIGHT = 'justify-end'
// Logical, so a column of Arabic aligns to the side its words start on. The
// header takes the same class as the cells.
const ALIGNED = { end: RIGHT, center: 'justify-center text-center' }
const aligned = (c) => ALIGNED[c.align] || ''

const PINNED = 'sticky z-10 bg-surface-base'

// The edge affordance: a hairline at whichever side has more beyond it.
//
// A border rather than a background, because the hairline wants the token the
// header band and the row dividers already draw — and that token is an
// *outline* colour, so `bg-outline-gray-2` is not a class at all and emitted no
// CSS. Above the sticky header's z-index, or it stops at the first row.
const EDGE = 'pointer-events-none absolute inset-y-0 z-30 w-0 border-l border-outline-gray-2'

// The band behind the column headers, and the reason `ListHeader`'s own rule is
// off: that rule is a grid child inset to the content box, so under a
// full-width fill it stopped short at both ends.
const BAND = [
  '[&_[data-slot=list-header]]:h-9',
  '[&_[data-slot=list-header]]:bg-surface-gray-1',
  '[&_[data-slot=list-header]]:border-b',
  '[&_[data-slot=list-header]]:border-outline-gray-2',
  '[&_[data-slot=list-header-border]]:hidden',
  // A group heading sticks *under* the column header rather than over it —
  // ListGroup pins at `top-0`, which is where the header already is.
  '[&_[data-slot=list-group-header]]:top-9',
].join(' ')

// What a row spends on things that are not columns: the checkbox inset, the row
// padding at both ends, and the column gap between every pair of tracks. Read
// off frappe-ui's own `style.css` rather than guessed — the first version
// forgot the gaps and left a horizontal scrollbar over nothing.
const CHECKBOX = 32
const ROW_PAD = 12 * 2
const COLUMN_GAP = 8

const scroller = ref(null)
// Whether there is more table beyond each edge. Both false on a table that fits.
const edges = ref({ left: false, right: false })
// How much room there is, measured by the same observer the edges use.
const paneWidth = ref(0)

const widened = computed(() => {
  const declared = props.columns || []
  if (!props.fill || declared.some((c) => !c.width)) return declared

  const fixed = declared.reduce((total, c) => total + c.width, 0)
  const gaps = Math.max(declared.length - 1, 0) * COLUMN_GAP
  const spent = (props.selectable ? CHECKBOX : 0) + ROW_PAD + gaps + fixed
  const slack = paneWidth.value - spent
  if (slack <= 0) return declared

  const grows =
    declared.find((c) => c.key === props.fill) || declared.find((c) => !c.pin) || declared[0]
  return declared.map((c) =>
    c === grows ? { ...c, width: c.width + slack, track: `${c.width + slack}px` } : c,
  )
})

const placed = computed(() => {
  const declared = widened.value

  // Where a pinned column starts, in pixels: a left pin sits past everything
  // pinned left before it, a right pin past everything pinned right after it.
  let fromLeft = 0
  const offsets = new Map()
  for (const column of declared) {
    if (column.pin !== 'left') continue
    offsets.set(column.key, fromLeft)
    fromLeft += column.width || 0
  }
  let fromRight = 0
  for (const column of [...declared].reverse()) {
    if (column.pin !== 'right') continue
    offsets.set(column.key, fromRight)
    fromRight += column.width || 0
  }

  return declared.map((column) => ({ ...column, offset: offsets.get(column.key) || 0 }))
})

const tracks = computed(() => placed.value.map((c) => c.track))

/**
 * Whether the tracks share the room they are given rather than each taking
 * what its content wants.
 *
 * `w-max` is right for the list: its columns are pixel widths a reader chose,
 * pinning is arithmetic over them, and a column narrower than its content is a
 * column somebody has to widen back. It is wrong for a child grid, where every
 * track is `minmax(_, 1fr)` and `1fr` against `max-content` resolves to the
 * content's width — a five-column grid of Selects came out 1250px wide inside a
 * 460px pane, and the three columns past the second, headers included, were
 * only reachable by scrolling.
 *
 * Read off the columns rather than passed: a set with no pixel widths is
 * exactly the set that has nothing to pin and nothing to fill.
 */
const shares = computed(() => (props.columns || []).every((c) => !c.width))

// A computed rather than an inline expression: a `>` inside a template
// attribute ends the tag as far as any regex-shaped parser is concerned.
const windowed = computed(
  () => !!props.virtualFrom && props.rows.length > props.virtualFrom,
)

const stickyStyle = (c) => (c.pin ? { [c.pin]: `${c.offset}px` } : undefined)

const sortField = computed(() => (props.orderBy || '').split(' ')[0])
const ascending = computed(() => (props.orderBy || '').split(' ')[1] === 'asc')

const directionFor = (c) => {
  if (c.key !== sortField.value) return undefined
  return ascending.value ? 'asc' : 'desc'
}

// A click on a cell rather than on the row.
//
// frappe-ui's `ListRow.onClick` returns before the app's handler ever runs when
// the list is selectable. Handled on the cell, stopping it here means `ListRow`
// never sees it; the checkbox keeps working because `ListRowBase` renders it as
// an absolutely-positioned sibling with its own `.stop` handler.
//
// A control inside the cell owns its own click: without this, liking a row
// would also open it.
const INTERACTIVE =
  'a[href], button, input, select, textarea, [role="checkbox"], [contenteditable="true"]'

const clicked = (row, index, event) => {
  if (event.target?.closest?.(INTERACTIVE)) return
  event.stopPropagation()
  emit('row-click', row, index)
}

// Read rather than tracked: a scroll position is the DOM's own state, and
// mirroring it into a ref is how the two end up disagreeing.
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

// The scroll width changes without a scroll: rows arriving, a column resized,
// the window narrowed. A ResizeObserver rather than a watcher and a nextTick,
// which measured a table that was not laid out yet.
const observer = new ResizeObserver(measureEdges)

watch(
  scroller,
  (el) => {
    observer.disconnect()
    if (!el) return
    // Both boxes: only one changes when the window narrows, and only the other
    // when a column is widened.
    observer.observe(el)
    if (el.firstElementChild) observer.observe(el.firstElementChild)
    measureEdges()
  },
  { flush: 'post' },
)

// The content's own width changes when rows arrive without the container
// resizing at all — an `auto` track sizing to a longer value.
watch([placed, () => props.rows], () => nextTick(measureEdges), { flush: 'post' })

onUnmounted(() => observer.disconnect())
</script>

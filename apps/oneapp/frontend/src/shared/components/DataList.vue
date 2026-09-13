<!--
  The frame around a list, wherever the rows come from.

  Seventeen surfaces draw a list and each built its own frame: a skeleton
  while it loads, an empty state when there is nothing, a count, a search box,
  a row. The rows differ — a file is not a thread is not a notification — and
  everything around them does not, which is why the audit's table of fourteen
  capabilities against those seventeen is almost entirely blank. Nothing had a
  way to ask for the frame.

  So the row is a slot and the frame is here. What a surface passes is a
  `ListSource` (`lib/list/source.js`): where the rows come from, what
  identifies one, and — §F1 — what it can do. A control this source cannot
  honour is not drawn; one it *refuses* is drawn, disabled, with the reason.

  It owns the *selection* too — which rows are ticked, what shift-click means,
  and dropping the ones a reload took away. What it does not own is where the
  bar saying so is drawn: Mail's list is a 384px column and the Drive's is the
  whole pane, so one centres over the window and the other over the column.
  That is a placement decision (§C2) and it stays with the surface, which
  renders `<SelectionBar>` where its own layout wants it.

  What this deliberately does **not** own is the record engine's own chrome —
  the view switcher, the filter panel, saved views, grouping. Those arrive
  with `DoctypeSource`, which is the last of the four on purpose.

  `docs/UNIFICATION.md` §B1.
-->
<template>
  <div class="flex min-h-0 flex-col" data-slot="data-list">
    <!--
      The header is the caller's, with the two things the source decides
      alongside: what to search in, and how many there are.
    -->
    <div
      v-if="$slots.header || can.has(CAN.SEARCH) || can.has(CAN.COUNT)"
      class="flex shrink-0 flex-wrap items-center gap-2 pb-3"
    >
      <slot
        name="header"
        :total="total"
        :chosen="chosen.size"
        :all-picked="allPicked"
        :toggle-all="toggleAll"
      />

      <!--
        Drawn here unless the caller took it. Binding `v-model:searched` means
        "my box, my place" — the Drive's lives in the page header beside
        Upload and New, which is a layout decision the frame has no business
        overruling. What stays the frame's either way is that a source which
        cannot be searched gets no box at all.
      -->
      <ListSearch
        v-if="can.can(CAN.SEARCH) && !theirs"
        v-model="mine"
        :placeholder="searchPlaceholder"
        @changed="read()"
      />
      <!--
        Refused rather than absent: said where the box would have been. A box
        drawn and disabled would be a second way to spell the same sentence,
        and `ListSearch` has no `disabled` — a prop added for one speculative
        caller is §F1's own mistake.
      -->
      <span v-else-if="can.why(CAN.SEARCH)" class="text-p-xs text-ink-muted">
        {{ can.why(CAN.SEARCH) }}
      </span>

      <span v-if="can.has(CAN.COUNT)" class="text-p-xs text-ink-muted tabular-nums">
        {{ counted }}
      </span>
    </div>

    <!--
      Bars at the height a row will be, so the page does not move when they
      arrive. The count is the caller's because only the caller knows how tall
      its own row is.
    -->
    <div v-if="waiting && !rows.length" class="flex flex-col gap-2" aria-hidden="true">
      <Skeleton v-for="n in skeleton" :key="n" :class="skeletonClass" />
    </div>

    <!--
      What nothing means here, from the source. A list that has been narrowed
      to nothing says something different from one that is empty — the first
      is a search to widen and the second is a place to put something.
    -->
    <!--
      A read that failed, said where the rows would have been. Every surface
      wrote this too, and half of them wrote it as a toast that is gone by the
      time anybody looks — §D2.
    -->
    <slot v-else-if="failure && !rows.length" name="failed" :message="failure">
      <Alert theme="red" :title="__('This did not load')" data-slot="data-list-failed">
        <template #description>{{ failure }}</template>
      </Alert>
    </slot>

    <!--
      The frame's own marker goes on a wrapper rather than on `EmptyState`.

      A `data-slot` passed down as a fallthrough attribute *replaces* the
      component's own — Vue merges `class` and `style` and nothing else — so
      `data-slot="empty-state"` stopped existing the day this moved into the
      frame, and every spec that looked for it quietly matched nothing instead
      of failing. Two hooks, because both claims are true: this is a list with
      nothing in it, and that is an empty state.
    -->
    <slot v-else-if="!rows.length" name="empty" :narrowed="!!asked">
      <div data-slot="data-list-empty">
        <EmptyState v-bind="asked ? narrowedFace : (source.empty || {})" />
      </div>
    </slot>

    <div v-else class="flex min-h-0 flex-col" :class="bodyClass">
      <!--
        `picked` and `toggle` come down with the row because a tick is drawn
        on it — a file row's checkbox, a conversation's — and the set it is
        ticked into is the frame's. A source that does not declare `bulk`
        answers `picked: false` and a `toggle` that does nothing, so a row
        component written for both surfaces needs no branch of its own.
      -->
      <slot
        v-for="(row, at) in rows"
        :key="source.identify(row)"
        name="row"
        :row="row"
        :index="at"
        :picked="chosen.has(source.identify(row))"
        :toggle="(event) => toggle(row, { range: !!event?.shiftKey })"
      />
    </div>

    <!-- One more page, where the source has one. -->
    <div v-if="more" class="shrink-0 pt-3">
      <Button
        variant="subtle"
        class="w-full"
        :label="__('Show more')"
        :loading="loading"
        data-slot="data-list-more"
        @click="read({ append: true })"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import { Alert, Button, Skeleton } from '@/ui'

import EmptyState from '@/shared/components/EmptyState.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import { CAN } from '@/shared/lib/capability'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** A `lib/list/source.js` implementation. */
  source: { type: Object, required: true },
  /** How many bars to draw while the first page is on its way. */
  skeleton: { type: Number, default: 3 },
  /** How tall one of them is — the caller's row, so the caller's height. */
  skeletonClass: { type: String, default: 'h-11 w-full' },
  /** What the rows sit in: a gap, a divider, a grid. */
  bodyClass: { type: String, default: '' },
  /** Rows per page, or 0 for all of them at once. */
  pageLength: { type: Number, default: 0 },
  /** What the box says before anybody types in it. */
  searchPlaceholder: { type: String, default: () => __('Search') },
})

/**
 * What is typed in the search box, when the caller draws the box.
 *
 * Unbound it is `undefined`, which is how this knows nobody took it and draws
 * its own. There is no third state: a caller either owns the control or does
 * not.
 */
const searched = defineModel('searched', { type: String, default: undefined })

const can = computed(() => props.source.can)

const rows = ref([])
const total = ref(0)
const more = ref(false)
const loading = ref(false)
const failure = ref('')
const mine = ref('')

const theirs = computed(() => searched.value !== undefined)
const asked = computed(() => (theirs.value ? searched.value : mine.value))

//: Either this frame is reading, or the caller that owns the rows still is.
//: A source that never says has nothing on its way, which is the honest
//: default for one built out of an array literal.
const waiting = computed(() => loading.value || !!props.source.busy?.())

const counted = computed(() =>
  total.value === 1 ? __('1 thing') : __('{0} things', [total.value]),
)

//: Narrowed to nothing is not the same as empty, and the difference is what
//: a person does next.
const narrowedFace = computed(() => ({
  icon: 'lucide-search-x',
  title: __('Nothing matches'),
  description: __('Try fewer words.'),
}))

/**
 * What is ticked, and it is the frame's.
 *
 * Three surfaces held this themselves — `useDrive`, `Mail.vue`, `useRows` —
 * and all three held the same four things: a `Set` of identities, a mapping
 * back to rows, a select-all, and an answer to "what happens to the ticks when
 * the rows are read again". The first three agreed. The fourth did not: the
 * Drive pruned what was gone, the record engine emptied the selection outright,
 * and Mail cleared it on the verb but not on a refresh — so the same four rows
 * re-read gave three different answers depending on which list you were in.
 *
 * By identity and never by row object, for the reason the Drive's own comment
 * gave: every mutation ends in a re-read, a re-read replaces every object, and
 * a selection held as objects empties itself on exactly the reload that
 * follows the action performed on it.
 *
 * Only ever *populated* where the source declares `CAN.BULK` — a surface that
 * cannot act on several rows has no business collecting them — which is
 * checked in `toggle` rather than at the call site, so a row that draws a tick
 * it should not have simply cannot fill it.
 */
const chosen = ref(new Set())

const identify = (row) => props.source.identify(row)

/** The rows themselves, for the verbs a bulk bar runs. */
const picked = computed(() => rows.value.filter((row) => chosen.value.has(identify(row))))

const allPicked = computed(
  () => rows.value.length > 0 && rows.value.every((row) => chosen.value.has(identify(row))),
)

//: Where the last tick was, so shift-clicking a second one takes everything
//: between. Not a ref: nothing renders from it.
let anchored = null

/**
 * Tick one, or everything between this one and the last.
 *
 * A new `Set` rather than mutating the one held: `Set` is not reactive in its
 * own right, and Mail's version — which did mutate — needed a `.size` read in
 * the template to redraw at all.
 */
function toggle(row, { range = false } = {}) {
  if (!can.value.can(CAN.BULK)) return
  const key = identify(row)
  const at = rows.value.findIndex((one) => identify(one) === key)
  const next = new Set(chosen.value)
  if (range && anchored !== null && at >= 0) {
    const [from, to] = anchored < at ? [anchored, at] : [at, anchored]
    for (const one of rows.value.slice(from, to + 1)) next.add(identify(one))
  } else if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  anchored = at
  chosen.value = next
}

/** Everything on screen, or nothing — whichever the tick is not already. */
function toggleAll() {
  if (!can.value.can(CAN.BULK)) return
  chosen.value = allPicked.value ? new Set() : new Set(rows.value.map(identify))
}

function clearChosen() {
  anchored = null
  chosen.value = new Set()
}

//: A row that is no longer here is not still ticked. Every bulk verb ends in
//: a re-read, and this is what stops the bar counting rows that were deleted
//: by the very action it ran.
function prune() {
  if (!chosen.value.size) return
  const here = new Set(rows.value.map(identify))
  const kept = [...chosen.value].filter((key) => here.has(key))
  if (kept.length !== chosen.value.size) chosen.value = new Set(kept)
}

/**
 * Ask the source.
 *
 * `append` is the only state this holds that the source does not: a page
 * arriving is rows *after* the ones on screen, and a source that returned the
 * whole list every time would make Show more a re-render rather than a read.
 * It is passed on as well as used, because not every source pages by offset —
 * a mailbox pages by cursor, and `start` means nothing to it.
 */
async function read({ append = false } = {}) {
  // A tick first, and it is not a hedge.
  //
  // A caller that owns the search box sets its own ref and then calls this in
  // the same handler — `ListSearch` emits `update:modelValue` and `changed`
  // back to back — so the parent's value is current and the *prop* carrying it
  // here is one render behind. Reading without waiting sends the previous
  // search, which for the first keystroke is no search at all: the Drive
  // narrowed to nothing and the list came back whole.
  await nextTick()
  loading.value = true
  failure.value = ''
  try {
    const answer = await props.source.load({
      append,
      start: append ? rows.value.length : 0,
      pageLength: props.pageLength,
      search: asked.value,
    })
    rows.value = append ? joined(answer.rows || []) : (answer.rows || [])
    total.value = answer.total ?? rows.value.length
    more.value = !!answer.hasMore
    prune()
  } catch (raised) {
    // Kept rather than thrown on: a list that could not be read is a state of
    // this list, and an unhandled rejection is a blank pane and a console
    // nobody is looking at.
    failure.value = errorText(raised)
    if (!append) { rows.value = []; total.value = 0; more.value = false }
  } finally {
    loading.value = false
  }
}

/**
 * The next page, after the ones on screen, with nothing twice.
 *
 * The dedupe is not defensive. A row can straddle two pages whenever the thing
 * being paged is not a fixed list — a conversation gains a message and moves,
 * a file is renamed and re-sorts — and appending blindly then shows it twice,
 * which is the bug Mail's own merge was written to avoid before there was one
 * frame to fix it in.
 *
 * Dropping the repeat is the *default* and not the rule, because for some
 * sources a row appearing twice carries information. A conversation that
 * straddles two pages of a mailbox has some of its messages in each, so the
 * two have to be added up rather than one thrown away — which is why a source
 * may answer `fold` and say how its own pages combine.
 */
function joined(arriving) {
  if (props.source.fold) return props.source.fold(rows.value, arriving)
  const here = new Set(rows.value.map((row) => props.source.identify(row)))
  return [...rows.value, ...arriving.filter((row) => !here.has(props.source.identify(row)))]
}

/**
 * Back to the top, with nothing typed.
 *
 * For a caller that is *reopened* rather than remounted — a picker behind an
 * Attach field, a panel that slides back in. Its source has not changed, so
 * the watch below does not fire, and without this it comes back showing the
 * last search somebody did in it.
 */
function reset() {
  if (theirs.value) searched.value = ''
  else mine.value = ''
  // A different list, so not the same ticks. Four files chosen in Home are not
  // four files chosen in the bin.
  clearChosen()
  return read()
}

// The source is a prop, so a caller that swaps it — a place in the Drive, a
// tab in the console — gets a fresh read rather than the last one's rows.
watch(() => props.source, reset, { immediate: true })

defineExpose({
  read, reset, rows, total, more, loading, failure,
  chosen, picked, allPicked, toggle, toggleAll, clearChosen,
})
</script>

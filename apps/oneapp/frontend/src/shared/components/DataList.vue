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
      <slot name="header" :total="total" />

      <ListSearch
        v-if="can.can(CAN.SEARCH)"
        v-model="asked"
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
    <slot v-else-if="!rows.length" name="empty" :narrowed="!!asked">
      <EmptyState
        v-bind="asked ? narrowedFace : (source.empty || {})"
        data-slot="data-list-empty"
      />
    </slot>

    <div v-else class="flex min-h-0 flex-col" :class="bodyClass">
      <slot
        v-for="(row, at) in rows"
        :key="source.identify(row)"
        name="row"
        :row="row"
        :index="at"
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
import { computed, ref, watch } from 'vue'

import { Button, Skeleton } from '@/ui'

import EmptyState from '@/shared/components/EmptyState.vue'
import ListSearch from '@/modules/onespace/components/screen/views/ListSearch.vue'
import { CAN } from '@/shared/lib/capability'
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

const can = computed(() => props.source.can)


const rows = ref([])
const total = ref(0)
const more = ref(false)
const loading = ref(false)
const asked = ref('')

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
 * Ask the source.
 *
 * `append` is the only state this holds that the source does not: a page
 * arriving is rows *after* the ones on screen, and a source that returned the
 * whole list every time would make Show more a re-render rather than a read.
 */
async function read({ append = false } = {}) {
  loading.value = true
  try {
    const answer = await props.source.load({
      start: append ? rows.value.length : 0,
      pageLength: props.pageLength,
      search: asked.value,
    })
    rows.value = append ? [...rows.value, ...(answer.rows || [])] : (answer.rows || [])
    total.value = answer.total ?? rows.value.length
    more.value = !!answer.hasMore
  } finally {
    loading.value = false
  }
}

// The source is a prop, so a caller that swaps it — a place in the Drive, a
// tab in the console — gets a fresh read rather than the last one's rows.
watch(() => props.source, () => { asked.value = ''; read() }, { immediate: true })

defineExpose({ read, rows, total })
</script>

<!--
  What is narrowing this list, and how to change it.

  There were two bars. `QuickFilters` read the doctype's own
  `in_standard_filter` fields and drew a `Select` or a text box per field in a
  bordered box; OneMobility's `FacetBar` drew a `Combobox` per facet as a
  subtle button that turned outline when set, with an X beside each set one, a
  Clear all, and one sentence naming what this view cannot answer.

  Neither was wrong. The facet bar had the better *interaction* — options you
  can search (a `Select` over forty lines is not a control), a clear per
  field, and a field the source has no column for shown disabled with the
  reason said once rather than silently missing. Quick filters had the better
  *source*: the doctype's own metadata, so nothing is declared twice.

  This is the first over the second. What a caller passes is a list of fields;
  where that list comes from is the caller's business — `in_standard_filter`
  for a doctype, `facets.offered()` for a fact table, a declared list for a
  file place.

  Two kinds of control, because there are two kinds of question. A Select or a
  Link is *chosen* from what exists, so it is a `Combobox`. A Data field is
  *typed*, because what you are looking for may not be there yet — and that
  one carries Frappe's own two operators beside it, equals or contains.

  `docs/UNIFICATION.md` §B2.
-->
<template>
  <div ref="bar" class="flex flex-wrap items-center gap-1.5" data-slot="narrow">
    <div v-for="one in shown" :key="one.key" class="flex items-center">
      <!-- Chosen from what exists. -->
      <!--
        `v-bind` and not four more attributes, because a field whose set is
        already here and one whose set is the server's are two different
        controls wearing one name. A static set is `Combobox`'s own business
        — it filters what it was given, and handing it a query to control
        would be taking that over for nothing. A loaded one is asked as the
        person types, so the query has to come back out.
      -->
      <Combobox
        v-if="one.kind !== 'type'"
        :model-value="chosen[one.key] ?? null"
        :options="optionsFor(one)"
        :placeholder="one.label"
        :empty-text="loading[one.key] ? __('Looking…') : __('Nothing to choose')"
        :disabled="unavailable.includes(one.key)"
        trigger="button"
        :variant="chosen[one.key] ? 'outline' : 'subtle'"
        size="sm"
        :data-slot="`narrow-${one.key}`"
        v-bind="one.load ? {
          query: asked[one.key] || '',
          filterable: false,
          loading: !!loading[one.key],
          'onUpdate:query': (value) => hunt(one, value),
        } : {}"
        @update:model-value="(value) => pick(one.key, value)"
      />

      <!-- Typed, because what you are looking for may not be there yet. -->
      <template v-else>
        <FormControl
          type="text"
          size="sm"
          :model-value="typed[one.key] ?? ''"
          :placeholder="one.label"
          :disabled="unavailable.includes(one.key)"
          class="w-36"
          :class="typed[one.key] && one.match && SQUARE_END"
          :data-slot="`narrow-${one.key}`"
          @update:model-value="(value) => (typed[one.key] = value)"
          @keydown.enter="pick(one.key, typed[one.key])"
          @blur="pick(one.key, typed[one.key])"
        />
        <!--
          Equals or contains, per box, and only once there is something in it:
          an empty box has nothing to match either way. The same two Frappe
          offers and the same two icons.
        -->
        <Dropdown v-if="one.match && typed[one.key]" :options="matchOptions(one)">
          <Button
            size="sm"
            :icon="match[one.key] === '=' ? 'lucide-equal' : 'lucide-equal-approximately'"
            :label="__('How {0} matches', [one.label])"
            :tooltip="__('How {0} matches', [one.label])"
            class="rounded-s-none"
          />
        </Dropdown>
      </template>

      <Button
        v-if="chosen[one.key]"
        class="-ms-1"
        variant="ghost"
        size="sm"
        icon="lucide-x"
        :label="__('Clear {0}', [one.label])"
        :tooltip="__('Clear {0}', [one.label])"
        @click="pick(one.key, null)"
      />
    </div>

    <Button
      v-if="anything"
      variant="ghost"
      size="sm"
      data-slot="narrow-clear"
      :label="__('Clear all')"
      icon-left="lucide-filter-x"
      @click="clearAll"
    />

    <!--
      Said once, at the end, rather than repeated on every disabled control:
      six tooltips carrying the same sentence is six chances to read it and
      one chance to notice it.
    -->
    <span v-if="unavailable.length" class="text-p-xs text-ink-muted">
      {{ __('Not available on this view: {0}', [missing]) }}
    </span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { Button, Combobox, Dropdown, FormControl } from '@/ui'

import { __ } from '@/shared/lib/runtime/translate'

// FormControl puts a class on its wrapper and the rounding is on the input
// inside it, so squaring the wrapper leaves the input round. Reach the input.
const SQUARE_END = '[&_input]:rounded-e-none'

const props = defineProps({
  /**
   * What can be narrowed by.
   *
   * `{ key, label, kind, options, load, match }` — `kind` is `'type'` for a
   * box somebody types in and anything else for one they choose from;
   * `options` is a static list and `load(query)` is the server's answer for a
   * set too big to send (a Link's rows, a facet's values); `match` says the
   * field takes Frappe's equals-or-contains pair.
   */
  fields: { type: Array, default: () => [] },
  /** Keys this source has no column for — disabled, with the reason once. */
  unavailable: { type: Array, default: () => [] },
  /**
   * How many controls to draw, or null for all of them.
   *
   * Measured rather than guessed, and measured against the *bar* rather than
   * the viewport: open a record beside a list and the same five controls
   * became two lines of empty boxes. The overflow is reported so a caller can
   * light the control that reveals the rest — that control lives in the
   * toolbar rather than at the end of a wrapping row, which is why the
   * expanded state comes in from outside.
   */
  measure: { type: Boolean, default: true },
})

const emit = defineEmits(['overflow'])

//: `{key: value}`, the flat shape. What a caller sends to its own server is
//: the caller's business — the engine turns this into Frappe operator tuples
//: and a fact table sends it as it is.
const chosen = defineModel({ type: Object, default: () => ({}) })
//: `{key: operator}`, for the fields that take one. Optional.
const match = defineModel('match', { type: Object, default: () => ({}) })
//: Whether the controls past the first are showing, on a phone.
const expanded = defineModel('expanded', { type: Boolean, default: false })

// What is in each typed box, which is not the same as what is applied: a box
// waits for Enter or a blur, because applying per keystroke is a request per
// keystroke.
const typed = reactive({})
// What each searchable Combobox has been asked, and what came back.
const asked = reactive({})
const found = reactive({})
const loading = reactive({})

const missing = computed(() =>
  props.fields
    .filter((one) => props.unavailable.includes(one.key))
    .map((one) => one.label)
    .join(', '),
)

const anything = computed(() => Object.values(chosen.value || {}).some((v) => v != null && v !== ''))

// ---------------------------------------------------------------- the room

//: One control's width, near enough. What matters is the count, and a
//: measured bar is the only thing that knows how much room a pane left it.
const BOX = 152
const bar = ref(null)
const width = ref(0)
let watcher = null

onMounted(() => {
  if (!props.measure || !bar.value || typeof ResizeObserver === 'undefined') return
  watcher = new ResizeObserver(([entry]) => { width.value = entry.contentRect.width })
  watcher.observe(bar.value)
})
onBeforeUnmount(() => watcher?.disconnect())

// Never fewer than one, and everything until it has been measured: a bar that
// measured itself at zero — which is what it measures before it is laid out —
// and drew nothing never comes back.
const fits = computed(() => {
  if (!props.measure || !width.value) return props.fields.length
  return Math.max(1, Math.floor((width.value + 8) / BOX))
})

const shown = computed(() =>
  expanded.value ? props.fields : props.fields.slice(0, fits.value),
)

watch(
  [() => props.fields, fits, expanded],
  () => emit('overflow', !expanded.value && props.fields.length > fits.value),
  { immediate: true },
)

// ------------------------------------------------------------ the controls

const optionsFor = (one) => (one.load ? found[one.key] || [] : one.options || [])

//: A field whose set is the server's is asked as the person types, debounced
//: once for the whole bar rather than once per control.
const PAUSE = 250
const waiting = {}

function hunt(one, value) {
  asked[one.key] = value
  if (!one.load) return
  window.clearTimeout(waiting[one.key])
  waiting[one.key] = window.setTimeout(async () => {
    loading[one.key] = true
    try {
      found[one.key] = (await one.load(value)) || []
    } catch {
      found[one.key] = []
    } finally {
      loading[one.key] = false
    }
  }, PAUSE)
}

const matchOptions = (one) =>
  [
    { value: '=', label: __('Equals') },
    { value: 'like', label: __('Contains') },
  ].map((option) => ({
    label: option.label,
    onClick: () => {
      match.value = { ...match.value, [one.key]: option.value }
      if (typed[one.key]) pick(one.key, typed[one.key])
    },
  }))

/**
 * Rebuilt rather than mutated: the parent holds this object and a watcher on
 * it is what refetches, so writing a key in place would change the value
 * without the list noticing.
 */
function pick(key, value) {
  const blank = value === null || value === undefined || value === ''
  typed[key] = value ?? ''
  // Nothing changed, so nothing is asked. A typed box applies on blur as well
  // as on Enter, and without this every tab out of an untouched box was a
  // request — which is how a list that nobody narrowed reloaded twice.
  if (blank ? !(key in chosen.value) : chosen.value[key] === value) return
  const next = { ...chosen.value }
  if (blank) delete next[key]
  else next[key] = value
  chosen.value = next
}

function clearAll() {
  Object.keys(typed).forEach((key) => { typed[key] = '' })
  chosen.value = {}
}

// Seeded from what came in, so a saved view opens with its own narrowing
// showing in the controls it came from.
watch(
  chosen,
  (now) => {
    for (const one of props.fields) {
      if (one.kind === 'type') typed[one.key] = now?.[one.key] ?? ''
    }
  },
  { immediate: true, deep: true },
)

//: The engine's filter panel reads what is in the boxes to know what the bar
//: is already covering.
defineExpose({ typed })
</script>

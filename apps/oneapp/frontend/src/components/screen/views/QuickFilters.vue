<template>
  <!--
    A box per field, above the list. Frappe's standard filter row: most of the
    time a person wants "the open ones", not a filter builder.

    Which fields get a box is the doctype's own decision —
    `in_standard_filter`, plus the title field — so no manifest repeats it. The
    ID box is always there, as it is in the desk.
  -->
  <div ref="row" class="flex flex-wrap items-center gap-2">
    <!--
      On a phone only the ID box stays and the toolbar's chevron reveals the
      rest, which is what Frappe's own mobile list does: five boxes stacked is
      most of the screen before a single row shows.
    -->
    <!-- As many as fit, and no more. See `fits`. -->
    <div
      v-for="quick in shown"
      :key="quick.key"
      class="flex items-stretch"
      :class="BOX"
    >
      <Select
        v-if="quick.options"
        :model-value="String(draft[quick.key] ?? '')"
        :options="quick.options"
        :placeholder="quick.label"
        class="w-full sm:w-36"
        @update:model-value="set(quick, $event)"
      />

      <template v-else>
        <FormControl
          type="text"
          :model-value="draft[quick.key] ?? ''"
          :placeholder="quick.label"
          class="min-w-0 flex-1 sm:w-36 sm:flex-none"
          :class="draft[quick.key] && quick.match && SQUARE_END"
          @update:model-value="set(quick, $event)"
          @keydown.enter="apply"
        />
        <!--
          Equals or contains, per box, remembered per screen — the same two
          Frappe offers and the same icons.

          Only once there is something in the box: an empty box has nothing to
          match either way.
        -->
        <Dropdown v-if="quick.match && draft[quick.key]" :options="matchOptions(quick)">
          <Button
            :icon="match[quick.key] === '=' ? 'lucide-equal' : 'lucide-equal-approximately'"
            :label="`How ${quick.label} matches`"
            :tooltip="`How ${quick.label} matches`"
            class="rounded-s-none"
          />
        </Dropdown>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Button, Dropdown, FormControl, Select } from '@/ui'
import { defaultOperator, operatorsFor } from '@/lib/screen/fields'

const props = defineProps({
  spec: { type: Object, required: true },
})
const emit = defineEmits(['changed', 'overflow'])

// What the person has typed, and how each box matches. Both keyed by fieldname,
// with `name` standing for the ID box.
// FormControl puts a class on its wrapper and the rounding is on the input
// inside it, so squaring the wrapper leaves the input round. Reach the input.
const SQUARE_END = '[&_input]:rounded-e-none'

// One box per line on a phone, each taking the width it is given. Anything else
// puts two boxes on the first line and squeezes the one people type in.
//
// A constant and not a comment inside the binding: the token audit reads a
// `:class` array as class names.
const BOX = 'basis-full sm:basis-auto'

/**
 * How many boxes there is room for, measured rather than guessed.
 *
 * What decides whether five boxes fit is the *pane*, not the viewport: open a
 * record beside the list and the same five became two lines of empty boxes.
 * Squeezing them was worse — a box whose placeholder reads "Alloca" is a box
 * nobody can use.
 *
 * The rest are not gone: the chevron in the toolbar reveals them, and every
 * column is in the filter panel besides. `expanded` shows them all and lets the
 * row wrap.
 */
const BOX_WIDTH = 152
const SIDE_BY_SIDE = '(min-width: 640px)'
const row = ref(null)
const width = ref(0)
const wide = ref(true)
let watcher = null
let media = null
const onMedia = () => (wide.value = media.matches)

onMounted(() => {
  // Below the breakpoint the boxes are full width and stack, so exactly one
  // fits however wide the row is — the same `sm:` that governs their layout.
  media = window.matchMedia(SIDE_BY_SIDE)
  onMedia()
  media.addEventListener('change', onMedia)

  if (!row.value || typeof ResizeObserver === 'undefined') return
  watcher = new ResizeObserver(([entry]) => {
    width.value = entry.contentRect.width
  })
  watcher.observe(row.value)
})

onBeforeUnmount(() => {
  watcher?.disconnect()
  media?.removeEventListener('change', onMedia)
})

// Never fewer than one: a row that measured itself at zero — which is what it
// measures before it is laid out — showing nothing at all never comes back.
const fits = computed(() => {
  if (!wide.value) return 1
  if (!width.value) return 99
  return Math.max(1, Math.floor((width.value + 8) / BOX_WIDTH))
})

// Whether the boxes past the first are showing. Only ever asked on a phone. The
// control that toggles it lives in the toolbar rather than at the end of a
// wrapping row of boxes, so the state comes in.
const expanded = defineModel('expanded', { type: Boolean, default: false })

const draft = reactive({})
const match = reactive({})

const columns = computed(() => props.spec?.all_columns || [])

const boxes = computed(() => {
  // The ID box first, as in the desk. `name` is not a column and never will
  // be, so it is described here rather than looked up.
  const found = [{ key: 'name', label: 'ID', match: true, fieldtype: 'Data' }]

  for (const fieldname of props.spec?.quick_filters || []) {
    const column = columns.value.find((c) => c.fieldname === fieldname)
    if (!column) continue
    const choices = (column.options || '').split('\n').filter(Boolean)
    found.push({
      key: fieldname,
      label: column.label,
      fieldtype: column.fieldtype,
      // A Select answers with its own options; blank means "any".
      options: column.fieldtype === 'Select' ? ['', ...choices] : null,
      // Only a box someone types into can be exact or roughly.
      match: column.fieldtype !== 'Select' && operatorsFor(column).includes('like'),
    })
  }
  return found
})

// What the row draws, and what is left over for the chevron to reveal.
const shown = computed(() => (expanded.value ? boxes.value : boxes.value.slice(0, fits.value)))

watch(
  [boxes, fits, expanded],
  () => emit('overflow', !expanded.value && boxes.value.length > fits.value),
  { immediate: true },
)

const matchOptions = (quick) =>
  [
    { value: '=', label: 'Equals' },
    { value: 'like', label: 'Like' },
  ].map((option) => ({
    label: option.label,
    onClick: () => {
      match[quick.key] = option.value
      if (draft[quick.key]) apply()
    },
  }))

const operatorFor = (quick) => {
  if (quick.options) return '='
  if (match[quick.key]) return match[quick.key]
  // Frappe's default for the type — text is a substring search, a link is not.
  const column = columns.value.find((c) => c.fieldname === quick.key)
  return column ? defaultOperator(column) : 'like'
}

const set = (quick, value) => {
  draft[quick.key] = value
  // A choice applies as soon as it is chosen; a box waits for Enter or a blur,
  // because applying per keystroke is a request per keystroke.
  if (quick.options || !value) apply()
}

const apply = () => {
  const filters = boxes.value
    .filter((quick) => draft[quick.key] !== '' && draft[quick.key] != null)
    .map((quick) => [quick.key, operatorFor(quick), draft[quick.key]])
  emit('changed', filters)
}

// Seeded from what the screen resolved to, so a saved view opens with its own
// filters showing in the boxes they came from.
watch(
  () => props.spec,
  (spec) => {
    Object.keys(draft).forEach((key) => delete draft[key])
    Object.keys(match).forEach((key) => delete match[key])
    for (const [fieldname, operator, value] of spec?.saved?.filters || []) {
      if (Array.isArray(value)) continue
      draft[fieldname] = value
      match[fieldname] = operator
    }
  },
  { immediate: true },
)

defineExpose({ draft })
</script>

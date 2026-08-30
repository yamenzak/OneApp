<template>
  <!--
    A box per field, above the list. Frappe's standard filter row, and it is
    worth copying because it answers the common case without opening anything:
    most of the time a person wants "the open ones", not a filter builder.

    Which fields get a box is the doctype's own decision — `in_standard_filter`,
    plus the title field — so no manifest repeats it. The ID box is always
    there, as it is in the desk.
  -->
  <div class="flex flex-wrap items-center gap-2">
    <!--
      On a phone only the ID box stays, and the toolbar's chevron reveals the
      rest — which is what Frappe's own mobile list does. Five boxes stacked is
      most of the screen before a single row shows, and hiding them with no way
      back was the half of that we had.
    -->
    <div
      v-for="(quick, index) in boxes"
      :key="quick.key"
      class="items-stretch"
      :class="[index === 0 || expanded ? 'flex' : 'hidden sm:flex', BOX]"
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
          :class="quick.match && SQUARE_END"
          @update:model-value="set(quick, $event)"
          @keydown.enter="apply"
        />
        <!--
          Equals or contains, per box, remembered per screen. The same two
          Frappe offers, and the same icons: `=` is exact, `≈` is roughly.
        -->
        <Dropdown v-if="quick.match" :options="matchOptions(quick)">
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
import { computed, reactive, watch } from 'vue'
import { Button, Dropdown, FormControl, Select } from '@/ui'
import { defaultOperator, operatorsFor } from '../../lib/fields'

const props = defineProps({
  spec: { type: Object, required: true },
})
const emit = defineEmits(['changed'])

// What the person has typed, and how each box matches. Both keyed by fieldname,
// with `name` standing for the ID box.
// FormControl puts a class on its wrapper, and the rounding is on the input
// inside it — so squaring the wrapper leaves the input round and the toggle
// button beside it looks bolted on. Reach the input.
const SQUARE_END = '[&_input]:rounded-e-none'

// One box per line on a phone, each taking the width it is given: the ID box
// alone on the first line with the row's three controls at its end, and the
// rest underneath it once they are revealed. Anything else puts two boxes on
// the first line and squeezes the one people actually type in. At a desktop
// width they sit side by side at a size of their own, because there they are
// alternatives rather than one search and some extras.
//
// A constant and not a comment inside the binding: the token audit reads a
// `:class` array as class names, and an English sentence in one is a hundred
// tokens that emit no CSS.
const BOX = 'basis-full sm:basis-auto'

// Whether the boxes past the first are showing. Only ever asked on a phone —
// above the breakpoint they are all there anyway. The control that toggles it
// belongs with the list's other controls rather than at the end of a wrapping
// row of boxes, so it lives in the toolbar and the state comes in.
const expanded = defineModel('expanded', { type: Boolean, default: false })

const draft = reactive({})
const match = reactive({})

const columns = computed(() => props.spec?.all_columns || [])

const boxes = computed(() => {
  // The ID box first, as in the desk. `name` is not a column and never will be,
  // so it is described here rather than looked up.
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

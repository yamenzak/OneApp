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
      On a phone only the ID box stays. Five boxes stacked is most of the screen
      before a single row shows, and Frappe makes the same call — its mobile
      list keeps the id filter and puts the rest behind a toggle. Here the rest
      are in the Filter panel, which a phone has room to open.
    -->
    <div
      v-for="(quick, index) in boxes"
      :key="quick.key"
      class="items-stretch"
      :class="index === 0 ? 'flex' : 'hidden sm:flex'"
    >
      <Select
        v-if="quick.options"
        :model-value="String(draft[quick.key] ?? '')"
        :options="quick.options"
        :placeholder="quick.label"
        class="w-36"
        @update:model-value="set(quick, $event)"
      />

      <template v-else>
        <FormControl
          type="text"
          :model-value="draft[quick.key] ?? ''"
          :placeholder="quick.label"
          class="w-36"
          :class="quick.match && 'rounded-e-none'"
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

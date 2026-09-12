<template>
  <!--
    A control per field, above the list. Frappe's standard filter row: most of
    the time a person wants "the open ones", not a filter builder.

    The bar itself is `shared/components/Narrow.vue` — the same one OneMobility
    narrows a fact table with. What is here is the *adapter*: which fields a
    doctype offers a control for, where each control's options come from, and
    how what somebody chose becomes the Frappe operator tuples the engine
    sends. That split is the whole of §B2: the interaction is one component
    and the source is whatever the surface has.

    Which fields get a control is the doctype's own decision —
    `in_standard_filter`, plus the ID box, which is always there as it is in
    the desk — so no manifest repeats it.
  -->
  <Narrow
    v-model="chosen"
    v-model:match="match"
    v-model:expanded="expanded"
    :fields="fields"
    @overflow="emit('overflow', $event)"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import Narrow from '@/shared/components/Narrow.vue'
import { defaultOperator, operatorsFor } from '@/modules/onespace/lib/screen/fields'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spec: { type: Object, required: true },
  spaceCode: { type: String, default: '' },
})
const emit = defineEmits(['changed', 'overflow'])

const expanded = defineModel('expanded', { type: Boolean, default: false })

// What is chosen, and how each typed box matches. Both keyed by fieldname,
// with `name` standing for the ID box.
const chosen = ref({})
const match = ref({})

const columns = computed(() => props.spec?.all_columns || [])

/**
 * The controls, and which kind each one is.
 *
 * A Select answers from its own options and a Link answers from the server's
 * — both are *chosen*, so both are a searchable list rather than the `Select`
 * a Select field used to get and the text box a Link used to get. A list of
 * forty options with no search is not a control, and a Link rendered as a
 * text box asked a customer to know a record's id.
 *
 * Everything else is *typed*, because what you are looking for may not be
 * there yet — and those carry Frappe's own equals-or-contains pair.
 */
const fields = computed(() => {
  // The ID box first, as in the desk. `name` is not a column and never will
  // be, so it is described here rather than looked up.
  const found = [{ key: 'name', label: __('ID'), kind: 'type', match: true }]

  for (const fieldname of props.spec?.quick_filters || []) {
    const column = columns.value.find((c) => c.fieldname === fieldname)
    if (!column) continue

    if (column.fieldtype === 'Select') {
      const choices = (column.options || '').split('\n').filter(Boolean)
      found.push({
        key: fieldname,
        label: column.label,
        options: choices.map((one) => ({ label: one, value: one })),
      })
      continue
    }

    if (column.fieldtype === 'Link') {
      found.push({
        key: fieldname,
        label: column.label,
        // Asked as the person types, through the same endpoint the Link
        // field's own picker uses — so it is bounded by the screen and runs
        // the reader's permissions, and a filter cannot offer a record they
        // could not have opened.
        load: (query) =>
          workspace.linkOptions(props.spaceCode, props.spec?.screen, fieldname, query),
      })
      continue
    }

    found.push({
      key: fieldname,
      label: column.label,
      kind: 'type',
      // Only a box someone types into can be exact or roughly.
      match: operatorsFor(column).includes('like'),
    })
  }
  return found
})

const operatorFor = (key) => {
  if (match.value[key]) return match.value[key]
  const column = columns.value.find((c) => c.fieldname === key)
  // Frappe's default for the type — text is a substring search, a link is not.
  return column ? defaultOperator(column) : 'like'
}

const tuples = () =>
  Object.entries(chosen.value)
    .filter(([, value]) => value !== '' && value != null)
    .map(([key, value]) => [key, operatorFor(key), value])

/**
 * What the screen last told the bar.
 *
 * The bar has two ways to change: a person uses a control, or the screen
 * resolves and seeds it with what was saved. The first is a request and the
 * second is not — a screen that answers its own seeding with "the filters
 * changed" is a screen that is dirty the moment it is saved, so Save never
 * turns into Undo.
 *
 * Compared rather than flagged: the assignment below is synchronous and the
 * watcher is not, so recording the state right after writing it is enough,
 * and there is no window where a real change is swallowed.
 */
const state = () => JSON.stringify([chosen.value, match.value])
let seeded = ''

// A change here is a request, so it goes out when the bar says something
// changed rather than on every keystroke — `Narrow` already waits for Enter
// or a blur on the boxes people type in. `match` as well as `chosen`, because
// equals-or-contains over the same text is a different question.
watch(
  [chosen, match],
  () => {
    if (state() === seeded) return
    emit('changed', tuples())
  },
  { deep: true },
)

// Seeded from what the screen resolved to, so a saved view opens with its own
// filters showing in the controls they came from.
watch(
  () => props.spec,
  (spec) => {
    const values = {}
    const operators = {}
    for (const [fieldname, operator, value] of spec?.saved?.filters || []) {
      if (Array.isArray(value)) continue
      values[fieldname] = value
      operators[fieldname] = operator
    }
    match.value = operators
    chosen.value = values
    seeded = state()
  },
  { immediate: true },
)
</script>

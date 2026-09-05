<template>
  <!--
    One filter: a field, an operator, and a value whose control follows from the
    two. Frappe's own shape, and the reason it is worth copying is that the
    third box is the hard part — "is set" needs no value, "between" needs two,
    "in" needs a list, and a Link needs a picker unless the operator is `like`,
    in which case it needs a text box.
  -->
  <div class="flex items-start gap-2">
    <!--
      Three boxes side by side need about thirty characters of room each. A
      phone has room for two of them, so the value gets its own line there
      rather than a box five characters wide.
    -->
    <div class="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start">
      <div class="flex min-w-0 gap-2">
        <Select
          :model-value="filter[0]"
          :options="fieldOptions"
          class="min-w-0 flex-1 sm:w-32 sm:flex-none"
          @update:model-value="pickField"
        />
        <Select
          :model-value="filter[1]"
          :options="operatorOptions"
          class="min-w-0 flex-1 sm:w-28 sm:flex-none"
          @update:model-value="pickOperator"
        />
      </div>

      <div class="min-w-0 flex-1">
        <!-- Set / Not Set. There is nothing else to say. -->
        <Select
          v-if="shape === 'set'"
          :model-value="filter[2]"
          :options="IS_OPTIONS"
          @update:model-value="pickValue"
        />

        <!-- Frappe's relative dates, handed to its own `timespan` operator. -->
        <Select
          v-else-if="shape === 'timespan'"
          :model-value="filter[2]"
          :options="TIMESPANS"
          @update:model-value="pickValue"
        />

        <DateRangePicker
          v-else-if="shape === 'range'"
          :model-value="rangeValue"
          placeholder="Pick two dates"
          @update:model-value="pickRange"
        />

        <!-- A choice, so a list of choices. -->
        <MultiSelect
          v-else-if="shape === 'multi' && choices.length"
          :model-value="listValue"
          :options="choices"
          @update:model-value="pickValue"
        />
        <FormControl
          v-else-if="shape === 'multi'"
          type="text"
          :model-value="listValue.join(', ')"
          placeholder="One, two, three"
          @update:model-value="pickList"
        />

        <!-- The same record picker the form uses, minus Create: nobody makes a
             record in order to filter by it. -->
        <LinkPicker
          v-else-if="shape === 'link'"
          :model-value="filter[2]"
          :fieldname="filter[0]"
          :space-code="spaceCode"
          :screen="screen"
          @update:model-value="pickValue"
        />

        <Select
          v-else-if="shape === 'choice'"
          :model-value="String(filter[2] ?? '')"
          :options="choices"
          @update:model-value="pickValue"
        />

        <FormControl
          v-else
          :type="plainType"
          :model-value="filter[2]"
          :placeholder="placeholder"
          @update:model-value="pickValue"
        />
      </div>
    </div>

    <Button
      icon="lucide-x"
      variant="ghost"
      label="Remove this filter"
      tooltip="Remove this filter"
      class="mt-0.5 shrink-0"
      @click="emit('remove')"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Select, MultiSelect, FormControl, DateRangePicker } from '@/ui'
import {
  CHECK_OPTIONS,
  IS_OPTIONS,
  TIMESPANS,
  defaultOperator,
  operatorLabel,
  operatorsFor,
  valueShape,
} from '../../../lib/fields'
import LinkPicker from '../fields/LinkPicker.vue'

const props = defineProps({
  // [fieldname, operator, value] — Frappe's own filter shape, and the server's.
  filter: { type: Array, required: true },
  columns: { type: Array, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
})
const emit = defineEmits(['update:filter', 'remove'])

// A field with no operators at all cannot be filtered — a child table is rows
// rather than a value — so it is not offered as one.
const filterable = computed(() => props.columns.filter((c) => operatorsFor(c).length))

const fieldOptions = computed(() =>
  filterable.value.map((c) => ({ value: c.fieldname, label: c.label })),
)

const field = computed(() => props.columns.find((c) => c.fieldname === props.filter[0]) || null)

const operatorOptions = computed(() =>
  operatorsFor(field.value).map((operator) => ({
    value: operator,
    label: operatorLabel(field.value, operator),
  })),
)

const shape = computed(() => valueShape(field.value, props.filter[1]))

const choices = computed(() => {
  if (field.value?.fieldtype === 'Check') return CHECK_OPTIONS
  return (field.value?.options || '')
    .split('\n')
    .filter(Boolean)
    .map((option) => ({ value: option, label: option }))
})

const listValue = computed(() => (Array.isArray(props.filter[2]) ? props.filter[2] : []))
const rangeValue = computed(() => (Array.isArray(props.filter[2]) ? props.filter[2].join(',') : ''))

// A Date under a comparison still wants a date box; everything else is text or
// a number, following what the field itself holds.
const NUMERIC = ['Int', 'Long Int', 'Float', 'Currency', 'Percent', 'Rating', 'Duration', 'Slider']
const plainType = computed(() => {
  const fieldtype = field.value?.fieldtype
  if (props.filter[1] === 'like' || props.filter[1] === 'not like') return 'text'
  if (fieldtype === 'Date') return 'date'
  if (fieldtype === 'Datetime') return 'datetime'
  if (fieldtype === 'Time') return 'time'
  if (NUMERIC.includes(fieldtype)) return 'number'
  return 'text'
})

const placeholder = computed(() =>
  ['like', 'not like'].includes(props.filter[1]) ? 'Contains…' : 'Value',
)

// What an empty value looks like for a shape, so switching operator does not
// leave a list sitting in a box that wants a word.
const blankFor = (nextShape) => {
  if (nextShape === 'set') return 'set'
  if (nextShape === 'range') return ['', '']
  if (nextShape === 'multi') return []
  return ''
}

const change = (next) => emit('update:filter', next)

const pickField = (fieldname) => {
  const next = props.columns.find((c) => c.fieldname === fieldname)
  const operator = defaultOperator(next)
  change([fieldname, operator, blankFor(valueShape(next, operator))])
}

const pickOperator = (operator) => {
  const wasShape = shape.value
  const nowShape = valueShape(field.value, operator)
  // Keep what was typed when the shape has not changed — swapping "Equals" for
  // "Not Equals" should not empty the box.
  const value = wasShape === nowShape ? props.filter[2] : blankFor(nowShape)
  change([props.filter[0], operator, value])
}

const pickValue = (value) => change([props.filter[0], props.filter[1], value])

const pickList = (text) =>
  change([
    props.filter[0],
    props.filter[1],
    String(text || '')
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean),
  ])

const pickRange = (value) => {
  const [from = '', to = ''] = String(value || '').split(',')
  change([props.filter[0], props.filter[1], [from.trim(), to.trim()]])
}
</script>

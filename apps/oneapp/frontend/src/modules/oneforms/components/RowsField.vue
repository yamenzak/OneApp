<template>
  <!--
    A repeating group on a page a stranger opened — an order's lines, a claim's
    expenses, a schedule of rates.
    `docs/ONEFORMS.md` §15, stage 16. It is the one control here that is not a
    field: the reader adds and removes rows, so the thing being edited is a
    *list* and the page has to say how long it is and let them change that.

    Drawn as stacked rows rather than a spreadsheet, and that is the phone
    deciding: a grid with five columns at 390px is five columns nobody can type
    in. On a desk the columns line up because the row is a grid; on a phone each
    row is a small stack with its own remove. One component, two readings.
  -->
  <div class="flex flex-col gap-2" :data-slot="`field-${field.fieldname}`">
    <span class="text-p-sm text-ink-secondary">
      {{ field.label }}<span v-if="field.reqd" class="text-ink-red-3"> *</span>
    </span>
    <p v-if="field.description" class="text-p-xs text-ink-muted">{{ field.description }}</p>

    <Panel
      v-for="(row, at) in rows"
      :key="at"
      ground="sunken"
      pad="tight"
      class="flex flex-col gap-2"
      :data-slot="`row-${field.fieldname}-${at}`"
    >
      <div class="grid gap-2" :class="ACROSS[Math.min(field.rows.length, 4)]">
        <FormControl
          v-for="column in field.rows"
          :key="column.fieldname"
          v-model="row[column.fieldname]"
          :type="control(column.fieldtype)"
          :label="column.label"
          :options="column.fieldtype === 'Select' ? choices(column) : undefined"
          :data-slot="`cell-${field.fieldname}-${column.fieldname}`"
          @update:model-value="changed"
        />
      </div>
      <Button
        class="self-start"
        variant="ghost"
        icon="lucide-x"
        :label="__('Take this row out')"
        :tooltip="__('Take it out')"
        :data-slot="`drop-${field.fieldname}`"
        @click="drop(at)"
      />
    </Panel>

    <Button
      class="self-start"
      icon-left="lucide-plus"
      :label="__('Add a row')"
      :disabled="rows.length >= (field.most || 100)"
      :data-slot="`add-${field.fieldname}`"
      @click="add"
    />
  </div>
</template>

<script setup>


import { Button, FormControl } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import { __ } from '@/shared/lib/runtime/translate'

//: Columns, by how many the row has. Written out rather than built from a
//: number: `grid-cols-${n}` is a class Tailwind's JIT never sees. From `md` up
//: only, which is where the shell switches — see `PublicForm.vue`.
const ACROSS = ['', '', 'md:grid-cols-2', 'md:grid-cols-3', 'md:grid-cols-4']

const props = defineProps({
  field: { type: Object, required: true },
  /** Which control a fieldtype gets — `PublicForm.vue` owns the map. */
  control: { type: Function, required: true },
})

const rows = defineModel({ type: Array, default: () => [] })

/** A Select's own options, off the child column's `options`. */
const choices = (column) =>
  String(column.options || '').split('\n').filter(Boolean)

/**
 * A new row, with every column present and empty.
 *
 * Present rather than absent: `v-model` on a key that does not exist yet makes
 * the row reactive only after the first keystroke, which loses that keystroke.
 */
const add = () => {
  rows.value = [
    ...rows.value,
    Object.fromEntries(props.field.rows.map((one) => [one.fieldname, ''])),
  ]
}

const drop = (at) => {
  rows.value = rows.value.filter((one, index) => index !== at)
}

// `defineModel` on an array does not see a key changing inside a row, so the
// assignment is what tells the page something moved.
const changed = () => { rows.value = [...rows.value] }
</script>

<template>
  <!--
    One band of the page: the header, a section of the body, or the footer.

    A band is a row of columns and a column is a stack of things, which is
    exactly what `format_data` holds — so the canvas is the layout laid out,
    with no model in between that could disagree with what prints.
  -->
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center gap-2">
      <span class="text-p-xs font-medium text-ink-gray-6">{{ label }}</span>
      <span v-if="hint" class="text-p-xs text-ink-gray-4">{{ hint }}</span>
      <span class="flex-1" />
      <Select
        :model-value="section.justify || ''"
        class="w-40"
        :options="JUSTIFY"
        @update:model-value="emit('justify', $event)"
      />
      <Button
        icon="lucide-columns-3"
        tooltip="Add a column"
        :disabled="section.columns.length >= 6"
        @click="addColumn"
      />
      <Button
        v-if="removable"
        icon="lucide-trash-2"
        tooltip="Remove this section"
        @click="emit('remove')"
      />
    </div>

    <div class="flex gap-2">
      <div
        v-for="(column, at) in section.columns"
        :key="at"
        class="flex min-h-[4rem] min-w-0 flex-1 flex-col gap-1 rounded-6 border border-dashed border-outline-gray-2 p-1.5"
        @dragover.prevent
        @drop.prevent="onto($event, at, column.fields.length)"
      >
        <div
          v-for="(field, row) in column.fields"
          :key="field._id"
          draggable="true"
          class="cursor-grab rounded-4 border px-2 py-1"
          :class="skin(at, row)"
          @dragstart="emit('carry', $event, { from: place(at, row) })"
          @dragover.prevent.stop
          @drop.prevent.stop="onto($event, at, row)"
          @click="emit('pick', address(zone, index0, at, row))"
        >
          <span class="block truncate text-p-xs text-ink-gray-8">{{ caption(field) }}</span>
          <span class="block truncate text-p-xs text-ink-gray-4">{{ note(field) }}</span>
        </div>

        <div
          v-if="!column.fields.length"
          class="flex flex-1 items-center justify-center text-p-xs text-ink-gray-4"
        >
          Drop here
        </div>

        <div class="flex items-center gap-1">
          <Button
            icon="lucide-minus"
            tooltip="Remove this column"
            :disabled="section.columns.length <= 1"
            @click="removeColumn(at)"
          />
          <Button
            icon="lucide-move-horizontal"
            tooltip="Make this column wider"
            @click="widen(at)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Select } from '@/ui'
import { address, emptyColumn } from './layout'

// Frappe's own four, because each names a CSS class in the generator's
// template and anything else is dropped there.
const JUSTIFY = [
  { label: 'Fill the row', value: '' },
  { label: 'Spread apart', value: 'space-between' },
  { label: 'Spread evenly', value: 'space-evenly' },
  { label: 'Centred', value: 'center' },
  { label: 'To the right', value: 'right-end' },
]

const props = defineProps({
  zone: { type: String, required: true },
  index: { type: Number, default: 0 },
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  section: { type: Object, required: true },
  selected: { type: String, default: '' },
  removable: { type: Boolean, default: false },
})

const emit = defineEmits(['drop-on', 'pick', 'carry', 'column', 'justify', 'remove'])

// The body's sections are addressed by their index; the two bands are not
// indexed at all, and carrying a stray number into their address would make
// two spellings of the same place.
const index0 = computed(() => (props.zone === 'sections' ? props.index : 0))

const place = (column, at) => ({
  zone: props.zone,
  section: index0.value,
  column,
  index: at,
})

const onto = (event, column, at) =>
  emit('drop-on', {
    ...place(column, at),
    raw: event.dataTransfer.getData('text/plain'),
  })

const skin = (column, at) =>
  props.selected === address(props.zone, index0.value, column, at)
    ? 'border-outline-gray-4 bg-surface-gray-2'
    : 'border-outline-gray-1 bg-surface-elevation-1'

const caption = (field) => field.label || field.fieldtype

const note = (field) => field.fieldname || field.fieldtype

/** Columns leave as a whole list, so the parent has one thing to apply. */
const columns = () => props.section.columns.map((one) => ({ ...one }))

const addColumn = () => emit('column', [...columns(), emptyColumn()])

const removeColumn = (at) => emit('column', columns().filter((one, at2) => at2 !== at))

/**
 * Wider by a step, and back to one when it has had four.
 *
 * `width` is a flex grow factor, so 1/1/1 is three equal columns and 2/1/1 is a
 * half and two quarters. A cycle rather than a number box: the useful values
 * are the first few integers and a spinner for them is three controls where
 * one press does.
 */
const widen = (at) =>
  emit(
    'column',
    columns().map((one, at2) => (at2 === at ? { ...one, width: ((one.width || 1) % 4) + 1 } : one)),
  )
</script>

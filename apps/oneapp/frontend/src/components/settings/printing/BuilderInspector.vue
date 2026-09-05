<template>
  <!--
    What the selected thing is, and the page it sits on.

    Two panels in one column rather than two tabs: the page setup is four
    numbers and is read while the element beside it is being placed, so
    hiding one behind the other costs a click on every adjustment.
  -->
  <div class="flex h-full flex-col gap-4 overflow-y-auto p-3">
    <div v-if="element" class="flex flex-col gap-3">
      <div class="flex items-center gap-2">
        <Icon name="lucide-square-pen" class="size-4 text-ink-gray-5" />
        <span class="text-p-sm font-medium text-ink-gray-8">
          {{ element.label || element.fieldtype }}
        </span>
      </div>

      <FormControl
        v-if="!isElement"
        :model-value="element.label"
        label="Label"
        @update:model-value="set('label', $event)"
      />

      <Switch
        v-if="!isElement"
        :model-value="element.show_label !== 'hide'"
        label="Show the label"
        @update:model-value="set('show_label', $event ? 'show' : 'hide')"
      />

      <FormControl
        v-if="element.fieldtype === 'HTML'"
        :model-value="element.html"
        type="textarea"
        label="HTML"
        :rows="6"
        description="Rendered as a template with the document in scope, so {{ doc.customer }} works."
        @update:model-value="set('html', $event)"
      />

      <FormControl
        v-if="element.fieldtype === 'Spacer'"
        :model-value="element.height"
        type="number"
        label="Height (px)"
        @update:model-value="set('height', Number($event))"
      />

      <template v-if="element.fieldtype === 'Image' || element.fieldtype === 'Barcode'">
        <Select
          :model-value="element.align || 'left'"
          label="Align"
          :options="ALIGN"
          @update:model-value="set('align', $event)"
        />
        <FormControl
          :model-value="element.width"
          label="Width"
          description="A CSS length — 40mm, 120px, 50%. Empty fits the column."
          @update:model-value="set('width', $event)"
        />
        <Select
          :model-value="element.fieldname || ''"
          :label="element.fieldtype === 'Image' ? 'From field' : 'Encode field'"
          :options="fieldOptions"
          @update:model-value="set('fieldname', $event)"
        />
        <FormControl
          v-if="element.fieldtype === 'Image'"
          :model-value="element.image_url"
          label="Or a fixed image URL"
          @update:model-value="set('image_url', $event)"
        />
      </template>

      <!--
        A child table prints as a table, so its columns are the thing worth
        setting. Checkboxes rather than a second drag surface: the order is the
        child doctype's own and reordering it here is a fourth place a column
        order can live.
      -->
      <div v-if="element.table_columns" class="flex flex-col gap-2">
        <span class="text-p-xs font-medium text-ink-gray-6">Columns</span>
        <Checkbox
          v-for="one in tableColumns"
          :key="one.fieldname"
          :model-value="one.on"
          :label="one.label"
          @update:model-value="toggleColumn(one, $event)"
        />
      </div>

      <Button
        icon-left="lucide-trash-2"
        label="Remove"
        @click="emit('remove')"
      />
    </div>

    <EmptyState
      v-else
      icon="lucide-mouse-pointer-click"
      title="Nothing selected"
      description="Pick something on the page to change what it says."
    />

    <div class="flex flex-col gap-3 border-t border-outline-gray-1 pt-4">
      <span class="text-p-xs font-medium text-ink-gray-6">The page</span>

      <div class="grid grid-cols-2 gap-2">
        <FormControl
          v-for="edge in EDGES"
          :key="edge.key"
          :model-value="setup[edge.key]"
          type="number"
          :label="edge.label"
          @update:model-value="page(edge.key, Number($event))"
        />
      </div>

      <FormControl
        :model-value="setup.font_size"
        type="number"
        label="Font size (pt)"
        @update:model-value="page('font_size', Number($event))"
      />

      <Select
        :model-value="setup.page_number"
        label="Page number"
        :options="PAGE_NUMBERS"
        @update:model-value="page('page_number', $event)"
      />

      <Switch
        :model-value="!!setup.align_labels_right"
        label="Align labels right"
        @update:model-value="page('align_labels_right', $event)"
      />

      <Switch
        :model-value="!!setup.show_label_colon"
        label="A colon after every label"
        @update:model-value="page('show_label_colon', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Checkbox, FormControl, Icon, Select, Switch } from '@/ui'
import EmptyState from '../../EmptyState.vue'

// Frappe's own words, because they are what the generator branches on.
const ALIGN = [
  { label: 'Left', value: 'left' },
  { label: 'Center', value: 'center' },
  { label: 'Right', value: 'right' },
]

const PAGE_NUMBERS = [
  'Hide',
  'Top Left',
  'Top Center',
  'Top Right',
  'Bottom Left',
  'Bottom Center',
  'Bottom Right',
].map((one) => ({ label: one, value: one }))

const EDGES = [
  { key: 'margin_top', label: 'Top margin (mm)' },
  { key: 'margin_bottom', label: 'Bottom (mm)' },
  { key: 'margin_left', label: 'Left (mm)' },
  { key: 'margin_right', label: 'Right (mm)' },
]

const props = defineProps({
  element: { type: Object, default: null },
  setup: { type: Object, required: true },
  palette: { type: Object, default: () => ({ fields: [], tables: [] }) },
})

// Every change leaves through here rather than being written onto the prop:
// the layout belongs to the builder, and an inspector that edits it in place
// is a second writer of one document.
const emit = defineEmits(['remove', 'set', 'page'])

const isElement = computed(() =>
  ['HTML', 'Spacer', 'Divider', 'Image', 'Barcode'].includes(props.element?.fieldtype),
)

const fieldOptions = computed(() => [
  { label: 'None', value: '' },
  ...(props.palette.fields || []).map((one) => ({ label: one.label, value: one.fieldname })),
])

/** The child's columns, each with whether this format prints it. */
const tableColumns = computed(() => {
  const table = (props.palette.tables || []).find(
    (one) => one.fieldname === props.element?.fieldname,
  )
  const held = new Set((props.element?.table_columns || []).map((one) => one.fieldname))
  return (table?.columns || []).map((one) => ({ ...one, on: held.has(one.fieldname) }))
})

const set = (key, value) => emit('set', key, value)

const page = (key, value) => emit('page', key, value)

/**
 * A child column on or off, sent as the whole list.
 *
 * The order is the child doctype's own, so a column switched back on returns
 * to where it was rather than to the end — which is what anybody who has just
 * switched one off by accident expects.
 */
const toggleColumn = (column, wanted) => {
  const held = new Set((props.element.table_columns || []).map((one) => one.fieldname))
  if (wanted) held.add(column.fieldname)
  else held.delete(column.fieldname)

  emit(
    'set',
    'table_columns',
    tableColumns.value
      .filter((one) => held.has(one.fieldname))
      .map(({ fieldname, label, fieldtype }) => ({ fieldname, label, fieldtype })),
  )
}
</script>

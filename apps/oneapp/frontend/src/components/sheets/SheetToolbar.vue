<template>
  <!--
    The formula bar and the format controls, in one band under the header.

    Two things, because they are two questions about the same cell: what is in
    it, and how it reads. The cell reference on the left is not decoration —
    it is the only place a person can see which cell a formula is being typed
    into once the grid has scrolled.
  -->
  <div data-slot="sheet-toolbar" class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-2">
    <div class="flex items-center gap-2">
      <Badge variant="subtle" theme="gray" :label="reference" class="w-24 shrink-0 justify-center" />
      <Icon name="lucide-function-square" class="size-4 shrink-0 text-ink-gray-5" />
      <FormControl
        v-model="typed"
        type="text"
        class="min-w-0 flex-1"
        placeholder="Value, or a formula starting with ="
        :disabled="!sheet.canWrite.value"
        aria-label="Formula bar"
        @keydown.enter="commit"
        @blur="commit"
      />
    </div>

    <!--
      Why the cell reads `#NAME?`. Here rather than on the cell, because a
      tooltip per cell is a component per cell, and there are twenty thousand
      of them. The bar already says which cell is selected, so this is the one
      place an explanation belongs.
    -->
    <p v-if="because" class="text-p-xs text-ink-red-4">{{ because }}</p>

    <div v-if="sheet.canWrite.value" class="flex flex-wrap items-center gap-1">
      <Button
        v-for="control in MARKS"
        :key="control.property"
        :icon="control.icon"
        :label="control.label"
        :tooltip="control.label"
        variant="ghost"
        :class="on(control.property) ? 'bg-surface-gray-3' : ''"
        @click="toggle(control.property)"
      />

      <Divider orientation="vertical" class="mx-1 h-5" />

      <Button
        v-for="control in ALIGNMENTS"
        :key="control.value"
        :icon="control.icon"
        :label="control.label"
        :tooltip="control.label"
        variant="ghost"
        :class="aligned(control.value) ? 'bg-surface-gray-3' : ''"
        @click="sheet.paint({ align: control.value })"
      />

      <Divider orientation="vertical" class="mx-1 h-5" />

      <Select
        :model-value="numberFormat"
        :options="FORMAT_OPTIONS"
        class="w-40"
        aria-label="Number format"
        @update:model-value="(code) => sheet.paint({ numFmt: code })"
      />

      <Divider orientation="vertical" class="mx-1 h-5" />

      <Button
        icon-left="lucide-brackets"
        label="Name this range"
        tooltip="Name this range"
        variant="ghost"
        @click="$emit('name-range')"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, Divider, FormControl, Icon, Select } from '@/ui'

import { NUMBER_FORMATS, parseFormat } from '../../lib/sheets/display'

const props = defineProps({
  sheet: { type: Object, required: true },
})

defineEmits(['name-range'])

const sheet = props.sheet

const MARKS = [
  { property: 'bold', icon: 'lucide-bold', label: 'Bold' },
  { property: 'italic', icon: 'lucide-italic', label: 'Italic' },
  { property: 'underline', icon: 'lucide-underline', label: 'Underline' },
  { property: 'wrap', icon: 'lucide-wrap-text', label: 'Wrap text' },
]

const ALIGNMENTS = [
  { value: 'left', icon: 'lucide-align-left', label: 'Align left' },
  { value: 'center', icon: 'lucide-align-center', label: 'Align centre' },
  { value: 'right', icon: 'lucide-align-right', label: 'Align right' },
]

const FORMAT_OPTIONS = NUMBER_FORMATS.map((one) => ({ label: one.label, value: one.code }))

// The bar holds a draft rather than binding straight to the cell: typing into
// it would otherwise recalculate the workbook on every keystroke, and half a
// formula is a formula that does not parse.
const typed = ref('')
watch(
  () => [sheet.cursor.value, sheet.formula.value, sheet.active.value],
  () => { typed.value = sheet.formula.value },
  { immediate: true },
)

const reference = computed(() => `${sheet.active.value}!${sheet.cursor.value}`)

const because = computed(() => sheet.current.value?.because || '')

const format = computed(() => parseFormat(sheet.current.value?.format))
const numberFormat = computed(() => format.value.numFmt || '')

function on(property) {
  return !!format.value[property]
}

function aligned(value) {
  return format.value.align === value
}

function toggle(property) {
  sheet.paint({ [property]: !format.value[property] })
}

function commit() {
  if (!sheet.canWrite.value) return
  if (typed.value === sheet.formula.value) return
  sheet.write([{ tab: sheet.active.value, ref: sheet.cursor.value, raw: typed.value }])
}
</script>

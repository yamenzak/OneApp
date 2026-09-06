<template>
  <!--
    The workspace's one colour.

    A row of colours to press and a hex to type, because both are real: most
    people want a colour that looks like theirs and a few have one written down
    to six digits. What is *not* here is a second theme editor — the workspace
    declares an accent and nothing else, for the same reason a space declares
    four words and not a stylesheet (`oneapp_core/theming.py`).

    The preview is the point of the control. `variables()` is the same mapping
    the document itself is painted with, so the button below is not an
    impression of the result — it is the result.
  -->
  <div class="flex flex-col gap-2">
    <FormLabel :label="label" />

    <div class="flex flex-wrap items-center gap-2">
      <Button
        v-for="one in PRESETS"
        :key="one"
        variant="ghost"
        class="size-7 rounded-full border border-outline-gray-2"
        :class="one === modelValue ? 'ring-2 ring-outline-gray-4 ring-offset-2' : ''"
        :style="{ backgroundColor: one }"
        :aria-label="one"
        :data-slot="`accent-${one.replace('#', '')}`"
        @click="modelValue = one"
      />

      <TextInput
        v-model="typed"
        class="w-28"
        placeholder="#0f62fe"
        aria-label="Brand colour as hex"
        data-slot="accent-hex"
        @blur="commit"
        @keydown.enter="commit"
      />

      <Button
        v-if="modelValue"
        variant="ghost"
        label="Clear"
        @click="modelValue = ''"
      />
    </div>

    <div class="flex items-center gap-3 pt-1">
      <Button variant="solid" label="Solid button" :style="preview" data-slot="accent-preview" />
      <p v-if="hint" class="text-p-sm text-ink-gray-5">{{ hint }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, FormLabel, TextInput } from '@/ui'
import { variables } from '@/lib/shell/theme'

defineProps({
  label: { type: String, required: true },
  hint: { type: String, default: '' },
})

const modelValue = defineModel({ type: String, default: '' })

/**
 * Ten to start from, spread around the wheel rather than sampled from one
 * palette: a workspace picking its colour is matching something it already has,
 * so the useful set is "somewhere near mine", not "nine shades of blue".
 */
const PRESETS = [
  '#0f62fe',
  '#1d4ed8',
  '#0e7490',
  '#047857',
  '#65a30d',
  '#ca8a04',
  '#ea580c',
  '#dc2626',
  '#be185d',
  '#7c3aed',
]

// What is in the box, which is not the value until it is a colour. Typing three
// characters of a hex must not repaint the page on each keystroke.
const typed = ref(modelValue.value)
watch(modelValue, (one) => (typed.value = one))

const commit = () => {
  const value = typed.value.trim().toLowerCase()
  const full = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/.test(value)
  if (full) modelValue.value = value.startsWith('#') ? value : `#${value}`
  else typed.value = modelValue.value
}

const preview = computed(() => variables({ accent: modelValue.value }))
</script>

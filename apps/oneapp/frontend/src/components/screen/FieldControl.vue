<template>
  <!--
    One field, rendered by whatever frappe-ui component its type maps to.

    The map is generated from Frappe's own fieldtype list (src/lib/fields.js), so
    a type nobody placed fails the build rather than quietly becoming a text box
    over a Currency column.
  -->
  <Combobox
    v-if="component === 'Combobox'"
    :model-value="modelValue"
    v-model:query="query"
    :options="options"
    :label="field.label"
    :placeholder="field.placeholder || 'Search…'"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Switch
    v-else-if="component === 'Switch'"
    :model-value="!!modelValue"
    :label="field.label"
    :description="field.description"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event ? 1 : 0)"
  />

  <Rating
    v-else-if="component === 'Rating'"
    :model-value="Number(modelValue) || 0"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Password
    v-else-if="component === 'Password'"
    :model-value="modelValue"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Duration
    v-else-if="component === 'Duration'"
    :model-value="Number(modelValue) || 0"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <MultiSelect
    v-else-if="component === 'MultiSelect'"
    :model-value="Array.isArray(modelValue) ? modelValue : []"
    :options="options"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <!--
    Attach and Attach Image. FileUploader takes a callback rather than a
    v-model — it hands back the File document, and what belongs in the field is
    its URL.
  -->
  <div v-else-if="component === 'FileUploader'" class="flex flex-col gap-1">
    <FormLabel :label="field.label" />
    <FileUploader
      :file-types="field.fieldtype === 'Attach Image' ? 'image/*' : undefined"
      @success="(file) => emit('update:modelValue', file.file_url)"
    >
      <template #default="{ openFileSelector }">
        <div class="flex items-center gap-2">
          <Button
            :label="modelValue ? 'Replace' : 'Upload'"
            :disabled="disabled"
            @click="openFileSelector"
          />
          <span v-if="modelValue" class="truncate text-p-sm text-ink-gray-6">
            {{ modelValue }}
          </span>
        </div>
      </template>
    </FileUploader>
  </div>

  <!--
    No frappe-ui counterpart: colour, signature, geolocation, barcode, icon.
    Shown, never offered — a text box that writes a hex string into a Signature
    field is worse than a value someone can read.
  -->
  <div v-else-if="!controlType" class="flex flex-col gap-1">
    <FormLabel :label="field.label" />
    <div class="flex items-center gap-2 rounded-4 bg-surface-gray-1 px-3 py-2">
      <span
        v-if="field.fieldtype === 'Color' && modelValue"
        class="size-4 shrink-0 rounded-full border border-outline-gray-2"
        :style="{ backgroundColor: modelValue }"
      />
      <span class="truncate text-p-sm text-ink-gray-7">{{ modelValue || '—' }}</span>
    </div>
    <p class="text-p-xs text-ink-gray-5">
      {{ field.fieldtype }} is shown here but edited elsewhere.
    </p>
  </div>

  <FormControl
    v-else
    :model-value="modelValue"
    :type="controlType"
    :label="field.label"
    :description="field.description"
    :placeholder="field.placeholder"
    :options="controlType === 'select' ? selectOptions : undefined"
    :required="!!field.reqd"
    :disabled="disabled"
    :rows="controlType === 'textarea' ? 3 : undefined"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  FormControl,
  FormLabel,
  Combobox,
  Switch,
  Rating,
  Password,
  Duration,
  MultiSelect,
  FileUploader,
  Button,
} from '@/ui'
import { controlComponent, formControlType } from '../../lib/fields'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  disabled: { type: Boolean, default: false },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const component = computed(() => controlComponent(props.field))
const controlType = computed(() => formControlType(props.field))

const selectOptions = computed(() => (props.field.options || '').split('\n').filter(Boolean))

// Link and Table MultiSelect both need a list to choose from, and a Link's list
// lives on the server behind the screen's own bounds.
const query = ref('')
const fetched = ref([])

const options = computed(() =>
  component.value === 'Combobox' && props.field.fieldtype !== 'Autocomplete'
    ? fetched.value
    : selectOptions.value,
)

const search = async () => {
  if (component.value !== 'Combobox' || props.field.fieldtype === 'Autocomplete') return
  fetched.value = await workspace.linkOptions(
    props.spaceCode,
    props.screen,
    props.field.fieldname,
    query.value,
  )
}

watch(query, search)
watch(() => props.field.fieldname, search, { immediate: true })
</script>

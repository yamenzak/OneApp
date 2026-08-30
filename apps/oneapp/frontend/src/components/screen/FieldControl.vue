<template>
  <!--
    One field, rendered by whatever frappe-ui component its type maps to.

    The map is generated from Frappe's own fieldtype list (src/lib/fields.js), so
    a type nobody placed fails the build rather than quietly becoming a text box
    over a Currency column.
  -->
  <!--
    A Link is a record, so it gets the record picker rather than a text box
    over a foreign key — searchable, showing a face and a name, and able to
    create one where the doctype and this person's permissions allow it.
  -->
  <LinkPicker
    v-if="component === 'Combobox'"
    :model-value="modelValue"
    :fieldname="field.fieldname"
    :space-code="spaceCode"
    :screen="screen"
    :label="field.label"
    :description="note"
    :placeholder="field.placeholder"
    :disabled="disabled"
    :required="!!field.reqd"
    :field="field"
    :is-new="isNew"
    allow-create
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Switch
    v-else-if="component === 'Switch'"
    :model-value="!!modelValue"
    :label="field.label"
    :description="note"
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

  <!--
    frappe-ui's Duration has no day unit at all — hours accumulate — so Frappe's
    `hide_days` is already how it behaves and only `hide_seconds` has anything
    to change here.
  -->
  <Duration
    v-else-if="component === 'Duration'"
    :model-value="Number(modelValue) || 0"
    :format="field.hide_seconds ? `h'h' m'm'` : 'short'"
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

  <!--
    The doctype's own bounds reach the control as attributes rather than as
    validation: `min`, `max` and `maxlength` are what make a field pleasant to
    type into, and the server enforces all three on save regardless. A browser
    makes typing pleasant; a database decides what is true.
  -->
  <FormControl
    v-else
    v-bind="bounds"
    :model-value="modelValue"
    :type="controlType"
    :label="field.label"
    :description="note"
    :placeholder="field.placeholder"
    :options="controlType === 'select' ? selectOptions : undefined"
    :required="!!field.reqd"
    :disabled="disabled"
    :rows="controlType === 'textarea' ? 3 : undefined"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup>
import { computed } from 'vue'
import {
  FormControl,
  FormLabel,
  Switch,
  Rating,
  Password,
  Duration,
  MultiSelect,
  FileUploader,
  Button,
} from '@/ui'
import LinkPicker from './LinkPicker.vue'
import { controlComponent, formControlType } from '../../lib/fields'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  disabled: { type: Boolean, default: false },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** A record being made rather than edited. Only the Link picker reads it,
      for `remember_last_selected_value`. */
  isNew: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const component = computed(() => controlComponent(props.field))
const controlType = computed(() => formControlType(props.field))

// A Select's own list. `sort_options` is the doctype asking for it
// alphabetically rather than in the order somebody typed it in, which is what
// the desk does and the only thing that flag means.
const selectOptions = computed(() => {
  const options = (props.field.options || '').split('\n').filter(Boolean)
  return props.field.sort_options ? [...options].sort((a, b) => a.localeCompare(b)) : options
})

/**
 * `min`, `max` and `maxlength`, where the doctype set them.
 *
 * Bound as an object because each is absent far more often than it is present,
 * and `:max="undefined"` on every number field is three attributes of noise for
 * the one doctype that uses them. `min_value`/`max_value` of 0 are real bounds
 * and travel as 0 — only null means unset.
 */
const bounds = computed(() => {
  const field = props.field
  const found = {}
  if (controlType.value === 'number') {
    if (field.non_negative) found.min = 0
    if (field.min_value !== null && field.min_value !== undefined) found.min = field.min_value
    if (field.max_value !== null && field.max_value !== undefined) found.max = field.max_value
  } else if (field.length) {
    found.maxlength = field.length
  }
  // Frappe's own ceiling on a text control, in pixels. Bound as a style rather
  // than a prop because no frappe-ui control takes a height: the textarea
  // still grows to it and then scrolls, which is what the flag asks for.
  if (field.max_height && controlType.value === 'textarea') {
    found.style = { maxHeight: `${parseInt(field.max_height, 10) || 0}px`, overflowY: 'auto' }
  }
  return found
})

/**
 * The line under the control.
 *
 * Three things can want to be there, and a field that says all three should
 * read as one sentence rather than three stacked notes:
 *
 *  - the doctype's own `description`
 *  - where a `fetch_from` value comes from, because a box that fills itself
 *    with no explanation is a box people retype. Frappe writes the source as
 *    `customer.customer_name`; the field it comes from is the half worth
 *    saying, and `fetch_if_empty` is the difference between "filled in once"
 *    and "replaced on every save"
 *  - that the value may not repeat, which is otherwise something you find out
 *    from a database error
 *
 * `show_description_on_click` moves the description behind the label's info
 * icon instead, which is the doctype saying it is long.
 */
const note = computed(() => {
  const field = props.field
  const parts = []

  if (field.description && !field.show_description_on_click) parts.push(field.description)

  if (field.fetch_from) {
    const from = String(field.fetch_from).split('.')[0].replace(/_/g, ' ')
    parts.push(field.fetch_if_empty ? `From ${from} if left blank` : `From ${from}`)
  }

  if (field.unique) parts.push('Must be unique')

  return parts.join(' · ') || undefined
})


// A Select and a Table MultiSelect both choose from the field's own `options`
// list. A Link does not — its list is records, which the picker fetches from
// the server behind the screen's own bounds.
const options = computed(() => selectOptions.value)
</script>

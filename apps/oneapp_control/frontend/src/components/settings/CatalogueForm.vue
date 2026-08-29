<template>
  <!-- Title and size are props, and the body is the default slot. The
       `:options` object and `#body-content` are frappe-ui v0 spelling: both
       are silently ignored, so the dialog opened with no heading and an
       empty body. -->
  <Dialog v-model="open" :title="title" size="lg">
    <div class="flex flex-col gap-4">
      <FormControl
        v-for="field in fields"
        :key="field.name"
        v-model="form[field.name]"
        :type="field.type || 'text'"
        :label="field.label"
        :options="field.options"
        :placeholder="field.placeholder"
        :description="field.hint"
        class="w-full"
      />
      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" :disabled="!complete" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl } from '@/ui'
import { callMethod } from '../../lib/resource'

/**
 * Create or edit one catalogue record.
 *
 * Generic on purpose: plans, regions and buckets are the same shape of task, and
 * three bespoke forms would be three places to forget a field. The desk is not
 * part of this product, so without something like this the catalogue could be
 * read and never populated — which leaves a control plane that cannot be
 * configured at all.
 */
const props = defineProps({
  doctype: { type: String, required: true },
  fields: { type: Array, required: true },
  // Existing record to edit; null creates a new one.
  record: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['saved'])

const form = reactive({})
const saving = ref(false)
const error = ref('')

const title = computed(() =>
  props.record ? `Edit ${props.doctype}` : `New ${props.doctype}`,
)

const complete = computed(() =>
  props.fields.filter((f) => f.required).every((f) => form[f.name]),
)

watch(
  [open, () => props.record],
  ([isOpen]) => {
    if (!isOpen) return
    error.value = ''
    for (const field of props.fields) {
      form[field.name] = props.record?.[field.name] ?? field.default ?? ''
    }
  },
  { immediate: true },
)

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (props.record) {
      // One call per changed field: set_value takes a mapping, and sending
      // untouched fields would stamp defaults over values set elsewhere.
      const changed = Object.fromEntries(
        props.fields
          .filter((f) => form[f.name] !== props.record[f.name])
          .map((f) => [f.name, form[f.name]]),
      )
      if (Object.keys(changed).length) {
        await callMethod('frappe.client.set_value', {
          doctype: props.doctype,
          name: props.record.name,
          fieldname: changed,
        })
      }
    } else {
      await callMethod('frappe.client.insert', {
        doc: { doctype: props.doctype, ...form },
      })
    }
    open.value = false
    emit('saved')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}
</script>

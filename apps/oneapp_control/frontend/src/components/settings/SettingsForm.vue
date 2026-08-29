<template>
  <div class="p-6">
    <SettingsHeader :title="title" :description="description" />

    <div class="mt-6 flex flex-col gap-5">
      <SettingsRow v-for="field in fields" :key="field.name" :label="field.label">
        <template #description>{{ field.hint }}</template>
        <FormControl
          v-model="form[field.name]"
          :type="field.type || 'text'"
          :placeholder="field.placeholder"
          :options="field.options"
          class="w-full"
        />
      </SettingsRow>
    </div>

    <div class="mt-6 flex items-center gap-2">
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
      <span v-if="dirty" class="text-p-sm text-ink-gray-5">Unsaved changes</span>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, FormControl, SettingsHeader, SettingsRow } from '@/ui'
import { callMethod } from '../../lib/resource'

/**
 * A settings panel backed by a Frappe Single doctype.
 *
 * Written once because every operator setting is the same shape: read the
 * single, edit fields, save. Doing it per panel is how six panels become six
 * slightly different save behaviours.
 */
const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  doctype: { type: String, required: true },
  fields: { type: Array, required: true },
})

const form = reactive({})
const original = ref({})
const saving = ref(false)

const dirty = computed(() =>
  props.fields.some((f) => form[f.name] !== original.value[f.name]),
)

async function load() {
  const doc = await callMethod(
    'frappe.client.get',
    { doctype: props.doctype, name: props.doctype },
    { silent: true },
  )
  for (const field of props.fields) {
    // Password fields come back masked; leaving the mask in the form would
    // write it back as the literal value on save.
    const value = field.type === 'password' ? '' : (doc?.[field.name] ?? '')
    form[field.name] = value
    original.value[field.name] = value
  }
}

async function save() {
  saving.value = true
  try {
    const changed = {}
    for (const field of props.fields) {
      // Only send what actually changed, so an untouched password field never
      // overwrites a stored secret with an empty string.
      if (form[field.name] !== original.value[field.name]) {
        changed[field.name] = form[field.name]
      }
    }
    if (!Object.keys(changed).length) return

    await callMethod(
      'frappe.client.set_value',
      { doctype: props.doctype, name: props.doctype, fieldname: changed },
      { successMessage: 'Settings saved' },
    )
    Object.assign(original.value, changed)
  } finally {
    saving.value = false
  }
}

watch(() => props.doctype, load, { immediate: true })
</script>

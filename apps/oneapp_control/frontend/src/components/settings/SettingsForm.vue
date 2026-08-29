<template>
  <SettingsHeader :title="title" :description="description" :class="PANEL_HEADER" />

  <SettingsBody :class="PANEL_BODY">
    <!--
      Stacked FormControls, not SettingsRow. SettingsRow is label-left /
      control-right with a `shrink-0` control and a `gap-8` between them — the
      shape frappe-ui uses for a Switch or a Select. Give it a full-width text
      input and on a phone the control keeps its width while the label column
      collapses, wrapping "API host" one word per line. frappe-ui's own
      ProfilePanel story stacks FormControls straight into SettingsBody for
      exactly this reason, and the label and description are FormControl's own
      props, so nothing is lost by dropping the row.
    -->
    <div class="flex max-w-xl flex-col gap-6 pt-6">
      <FormControl
        v-for="field in fields"
        :key="field.name"
        v-model="form[field.name]"
        :type="field.type || 'text'"
        :label="field.label"
        :description="field.hint"
        :placeholder="field.placeholder"
        :options="field.options"
      />
    </div>
  </SettingsBody>

  <!-- Pinned, not the last thing in the scroll region: on a phone a long form
       puts Save below the fold exactly when there is something to save. -->
  <div :class="PANEL_FOOTER">
    <Button variant="solid" label="Save" :loading="saving" :disabled="!dirty" @click="save" />
    <span v-if="dirty" class="text-p-sm text-ink-gray-5">Unsaved changes</span>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, FormControl, SettingsHeader, SettingsBody } from '@/ui'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { useDocument, useDocWrites } from '../../lib/resource'

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

// A Single's document name is the doctype's own name. `doctype` is fixed per
// panel, so it is passed as a value — only `name` accepts a getter.
const record = useDocument(props.doctype, props.doctype, { silent: true })
const writes = useDocWrites(props.doctype, { successMessage: 'Settings saved' })

// The document arrives asynchronously, and again after every save, so the form
// is filled from it reactively rather than fetched imperatively once.
watch(
  () => record.doc,
  (doc) => {
    for (const field of props.fields) {
      // Password fields come back masked; leaving the mask in the form would
      // write it back as the literal value on save.
      const value = field.type === 'password' ? '' : (doc?.[field.name] ?? '')
      form[field.name] = value
      original.value[field.name] = value
    }
  },
  { immediate: true },
)

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

    await writes.setValue({ name: props.doctype, ...changed })
    Object.assign(original.value, changed)
  } finally {
    saving.value = false
  }
}
</script>

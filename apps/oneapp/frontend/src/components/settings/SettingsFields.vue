<template>
  <SettingsHeader :title="group.label" :description="group.description" :class="PANEL_HEADER" />

  <SettingsBody :class="PANEL_BODY">
    <!--
      Rendered from the server's own spec rather than from a list here. That
      spec is also the allowlist the save path checks against, so a field a page
      invented would be refused rather than silently written — and a field added
      server-side appears without a second edit.
    -->
    <div class="flex max-w-xl flex-col gap-6 pt-6">
      <template v-for="field in group.fields" :key="field.key">
        <Switch
          v-if="field.type === 'Check'"
          v-model="form[field.key]"
          :label="field.label"
          :description="field.hint"
          padded
        />
        <FormControl
          v-else
          v-model="form[field.key]"
          :type="control(field)"
          :label="field.label"
          :description="field.hint"
          :placeholder="field.placeholder"
          :options="field.options || undefined"
        />
      </template>
    </div>
  </SettingsBody>

  <div :class="PANEL_FOOTER">
    <Button variant="solid" label="Save" :loading="saving" :disabled="!dirty" @click="save" />
    <span v-if="dirty" class="text-p-sm text-ink-gray-5">Unsaved changes</span>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, FormControl, SettingsHeader, SettingsBody, Switch } from '@/ui'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'

const props = defineProps({ group: { type: Object, required: true } })
const emit = defineEmits(['saved'])

const form = reactive({})
const original = ref({})
const saving = ref(false)

// A Link is a text box here rather than a Link control: the workspace owner is
// not a System Manager, so `search_link` refuses them, and a picker that cannot
// search is worse than a field that says what it wants. The server validates
// the value against the doctype either way.
const control = (field) =>
  ({ Select: 'select', Int: 'number', 'Attach Image': 'text' })[field.type] || 'text'

const dirty = computed(() =>
  props.group.fields.some((f) => form[f.key] !== original.value[f.key]),
)

watch(
  () => props.group,
  (group) => {
    for (const field of group.fields) {
      const value = field.type === 'Check' ? Boolean(field.value) : (field.value ?? '')
      form[field.key] = value
      original.value[field.key] = value
    }
  },
  { immediate: true, deep: true },
)

async function save() {
  saving.value = true
  try {
    const changed = Object.fromEntries(
      props.group.fields
        .filter((f) => form[f.key] !== original.value[f.key])
        .map((f) => [f.key, form[f.key]]),
    )
    if (!Object.keys(changed).length) return
    await workspace.save(props.group.key, changed)
    Object.assign(original.value, changed)
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

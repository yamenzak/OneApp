<template>
  <SettingsHeader :title="group.label" :description="group.description" :class="PANEL_HEADER" />

  <SettingsBody :class="PANEL_BODY">
    <!--
      Rendered from the server's own spec rather than from a list here. That
      spec is also the allowlist the save path checks against, so a field a page
      invented would be refused rather than silently written — and a field added
      server-side appears without a second edit.
    -->
    <!--
      One column, or two where the group asks for them. `grid` and not two
      stacked flex columns: a grid keeps the rows aligned across the gutter, so
      a hint that wraps to a second line on the left does not push the right
      column out of step with it. Always one on a phone, whatever was declared.
    -->
    <div :class="LAYOUT[group.columns] || LAYOUT[1]">
      <!--
        Something true about this group that is not a field. Sign in has the
        only one: there is no sign-up switch, and this is where somebody looks
        for it. A note rather than a disabled control, because the answer is not
        "off" — it is that accounts are made somewhere else.
      -->
      <div
        v-if="group.note"
        class="flex flex-col gap-1 rounded-6 border border-outline-gray-2 bg-surface-gray-1 p-3 sm:col-span-full"
        data-slot="settings-note"
      >
        <p class="text-base-medium text-ink-gray-8">{{ group.note.title }}</p>
        <p class="text-p-sm text-ink-gray-6">{{ group.note.body }}</p>
        <a
          v-if="group.note.link"
          :href="group.note.link"
          target="_blank"
          rel="noopener"
          class="mt-1 text-p-sm text-ink-blue-link hover:underline"
        >{{ group.note.link_label }}</a>
      </div>

      <template v-for="field in shown" :key="field.key">
        <Switch
          v-if="field.type === 'Check'"
          v-model="form[field.key]"
          :label="field.label"
          :description="field.hint"
          padded
        />
        <!--
          A file, picked rather than typed. These were text boxes: the map below
          sent `Attach Image` to `text`, so setting a logo meant knowing the
          `/files/...` URL of something already uploaded — which nothing in this
          product tells you. The same picker a record's Attach field opens, so a
          logo and an invoice's attachment are chosen the same way.
        -->
        <SettingsAttach
          v-else-if="field.type === 'Attach' || field.type === 'Attach Image'"
          v-model="form[field.key]"
          :label="field.label"
          :hint="field.hint"
          :image="field.type === 'Attach Image'"
        />
        <!--
          A colour, which frappe-ui has no control for. See SettingsColour.vue
          for why the workspace gets one accent and not a theme editor.
        -->
        <SettingsColour
          v-else-if="field.type === 'Color'"
          v-model="form[field.key]"
          :label="field.label"
          :hint="field.hint"
        />
        <FormControl
          v-else
          :model-value="draw(field)"
          @update:model-value="form[field.key] = $event"
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
import SettingsAttach from './SettingsAttach.vue'
import SettingsColour from './SettingsColour.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { setBrand } from '../../lib/shell/theme'
import { workspace } from '../../lib/workspace'

/**
 * How wide the form is and how it is divided, by the number of columns the
 * group asked for. A map rather than a template expression because Tailwind
 * reads this file for the classes it emits: a class assembled at runtime is a
 * class that is not in the stylesheet.
 */
const LAYOUT = {
  1: 'grid max-w-xl grid-cols-1 gap-6 pt-6',
  2: 'grid max-w-3xl grid-cols-1 gap-x-10 gap-y-6 pt-6 sm:grid-cols-2',
}

const props = defineProps({ group: { type: Object, required: true } })
const emit = defineEmits(['saved'])

const form = reactive({})
const original = ref({})
const saving = ref(false)

// There is no Link control here, and no setting declares one — a guard in
// `tests/test_workspace_settings.py` holds that. The picker that would make a
// Link a Link cannot run: `search_link` refuses a workspace owner, who is
// deliberately not a System Manager, so a Link fell through this map to `text`
// and became a box you had to already know the exact spelling for. The five
// settings that were Links are Selects fed from their own doctype instead —
// see `workspace.reference`.
const control = (field) =>
  ({ Select: 'select', Int: 'number', Float: 'number' })[field.type] || 'text'

const numeric = (field) => field.type === 'Int' || field.type === 'Float'

/**
 * What goes in the box, which is not always what is stored.
 *
 * Zero is how Frappe says "not set" on several numeric columns — a font size of
 * 0 renders at 14, a custom page width of 0 is no width — and a settings form
 * that draws a 0 there is showing a value nobody chose as though somebody had.
 * Where a setting declares what it falls back to, the zero is the placeholder
 * instead. Empty comes back as 0, which is the same "not set" going the other
 * way.
 */
const draw = (field) =>
  numeric(field) && field.placeholder && !form[field.key] ? '' : form[field.key]

/**
 * The fields to draw, which is not all of them: a setting may name another in
 * the same group as the switch it hangs off, and a second factor nobody can
 * reach is a control that does nothing. With `depends_value` the parent has to
 * hold exactly that — a custom page width belongs to the page size being
 * Custom, not to it being anything at all.
 *
 * Read off `form` and not off the server's values, so turning the parent on
 * reveals the child immediately rather than after a save and a reload.
 */
const visible = (field) => {
  if (!field.depends_on) return true
  const parent = form[field.depends_on]
  return field.depends_value == null ? Boolean(parent) : parent === field.depends_value
}

const shown = computed(() => props.group.fields.filter(visible))

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
    // `type="number"` still hands back a string and the column behind it is a
    // Float or an Int. Frappe coerces, but a decimal reaching a Float as text
    // is a round trip nobody should have to rely on.
    const changed = Object.fromEntries(
      props.group.fields
        .filter((f) => form[f.key] !== original.value[f.key])
        .map((f) => [f.key, numeric(f) ? Number(form[f.key] || 0) : form[f.key]]),
    )
    if (!Object.keys(changed).length) return
    await workspace.save(props.group.key, changed)
    Object.assign(original.value, changed)

    // The one setting that changes the page it was set on. Repainted here
    // rather than on every keystroke in the picker, so abandoning the dialog
    // leaves the workspace the colour it actually is.
    const colour = props.group.fields.find((f) => f.type === 'Color' && f.key in changed)
    if (colour) setBrand({ accent: changed[colour.key] })

    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <!--
    A record's fields, laid out the way the doctype lays them out.

    The tabs and sections are the doctype's own — Frappe's desk reads `Tab
    Break` and `Section Break` out of the field list and so does this, which is
    why a doctype whose author grouped its fields is grouped the same way here
    without a manifest repeating any of it. A doctype that groups nothing has
    one tab called Details and no headings at all, so a small form stays a
    small form.

    Not the settings dialog's left rail: that shape earns its place over a
    dozen unrelated pages, and a record with two tabs beside a rail reads as a
    page that lost its content. The doctype says how many there are, so the
    layout follows it rather than fixing one shape for every doctype.
  -->
  <Tabs v-if="tabs.length > 1" v-model="tab">
    <TabList>
      <TabTrigger v-for="one in tabs" :key="one.key" :value="one.key">
        {{ one.label }}
      </TabTrigger>
    </TabList>
    <TabPanel v-for="one in tabs" :key="one.key" :value="one.key">
      <div class="pt-4">
        <FormSections v-model:values="values" :sections="one.sections" v-bind="passthrough" />
      </div>
    </TabPanel>
  </Tabs>

  <!-- One tab is not a tab. A strip with a single word on it is chrome that
       says nothing and takes a row to say it. -->
  <FormSections
    v-else
    v-model:values="values"
    :sections="tabs[0]?.sections || []"
    v-bind="passthrough"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Tabs, TabList, TabTrigger, TabPanel } from '@/ui'
import FormSections from './FormSections.vue'

const props = defineProps({
  /** The screen spec: `form` for the layout, `all_columns` for the fields. */
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether anything here may be written at all. */
  disabled: { type: Boolean, default: false },
  /** A record being made rather than edited: `set_only_once` is not yet spent. */
  isNew: { type: Boolean, default: false },
})

/** The values being edited, keyed by fieldname. */
const values = defineModel('values', { type: Object, required: true })

const tab = ref('t0')

const columns = computed(() => {
  const found = {}
  for (const column of props.spec?.all_columns || props.spec?.columns || []) {
    found[column.fieldname] = column
  }
  return found
})

// The layout, resolved against the columns. A fieldname the spec no longer
// offers — a field renamed on the site, a permlevel this person cannot read —
// drops out here rather than rendering a control over nothing.
const tabs = computed(() =>
  (props.spec?.form || [])
    .map((one) => ({
      ...one,
      sections: one.sections
        .map((section) => ({
          ...section,
          fields: section.fields.map((name) => columns.value[name]).filter(Boolean),
        }))
        .filter((section) => section.fields.length),
    }))
    .filter((one) => one.sections.length),
)

const passthrough = computed(() => ({
  spaceCode: props.spaceCode,
  screen: props.screen,
  disabled: props.disabled,
  isNew: props.isNew,
}))

// Back to the first tab whenever the form is for something else. Landing on
// tab four of the record you just closed is a small thing that reads as a bug.
watch(
  () => [props.spec?.screen, props.isNew],
  () => {
    tab.value = tabs.value[0]?.key || 't0'
  },
)
</script>

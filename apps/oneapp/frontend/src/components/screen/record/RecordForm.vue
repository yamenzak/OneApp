<template>
  <!--
    A record's fields, laid out the way the doctype lays them out.

    The tabs and sections are the doctype's own — Frappe's desk reads `Tab
    Break` and `Section Break` out of the field list and so does this, which is
    why a doctype whose author grouped its fields is grouped the same way here
    without a manifest repeating any of it. The glyph on each is derived from
    the tab's own label: Frappe has no icon property on a Tab Break, so a form
    laid out by somebody who never heard of OneSpace still reads as a strip of
    tabs rather than a row of bare words. A manifest may override one.

    A doctype that groups nothing has one tab called Details and no headings at
    all, so a small form stays a small form.

    A pill track rather than the underline the record's own strip uses, and that
    is the whole of the fix: these two sit an inch apart, both opened with the
    word Details, and drawn as two identical underlined rows they read as one
    strip that had been split in half. They are not siblings — the record's
    strip moves between the record and everything filed against it, this one
    moves inside one of those — so the two should not look alike. `subtle` is
    frappe-ui's own answer for a secondary strip, so the difference is the
    library's rather than a border somebody chose.

    Not the settings dialog's left rail: that shape earns its place over a
    dozen unrelated pages, and a record with two tabs beside a rail reads as a
    page that lost its content. The doctype says how many there are, so the
    layout follows it rather than fixing one shape for every doctype.
  -->
  <Tabs v-if="tabs.length > 1" v-model="tab">
    <!--
      And it scrolls sideways rather than running off the edge. A doctype that
      declares six tabs declares six of them whatever it is being drawn in, and
      a Sales Invoice in a 480-pixel pane had its last two past the right edge
      with nothing to say so. The same wrapper the record's own strip has, for
      the same reason.
    -->
    <div class="overflow-x-auto">
      <TabList variant="subtle">
        <TabTrigger
          v-for="one in tabs"
          :key="one.key"
          :value="one.key"
          :label="one.label"
          :icon-left="tabIcon(one.label, spec.tab_icons)"
        />
      </TabList>
    </div>
    <TabPanel v-for="one in tabs" :key="one.key" :value="one.key">
      <div class="pt-4">
        <FormSections
          v-model:values="values"
          :sections="one.sections"
          v-bind="passthrough"
          @reload="emit('reload')"
        />
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
    @reload="emit('reload')"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Tabs, TabList, TabTrigger, TabPanel } from '@/ui'
import FormSections from './FormSections.vue'
import { tabIcon } from '../../../lib/fields'

const props = defineProps({
  /** The screen spec: `form` for the layout, `all_columns` for the fields. */
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether anything here may be written at all. */
  disabled: { type: Boolean, default: false },
  /** A record being made rather than edited: `set_only_once` is not yet spent. */
  isNew: { type: Boolean, default: false },
  /**
   * The record's id, where it has one.
   *
   * Passed in rather than read off `values.name`, which is empty: the draft
   * holds one key per docfield and `name` is not a docfield. The controls that
   * write through the server rather than through the form — attaching a file,
   * filling a child table from a sheet — need the id of the thing they are
   * writing to.
   */
  docname: { type: String, default: '' },
})

/** The values being edited, keyed by fieldname. */
const emit = defineEmits(['reload'])

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
          columns: section.columns
            .map((column) =>
              column
                // A string is a fieldname to resolve; an object is a Heading or
                // an HTML block the doctype wrote, which has nothing to resolve
                // against. See `_form` in `spaceview/meta.py`.
                .map((entry) => (typeof entry === 'string' ? columns.value[entry] : entry))
                .filter(Boolean),
            )
            // A column of nothing but headings is a heading over nothing.
            .filter((column) => column.some((entry) => !entry.note)),
        }))
        .filter((section) => section.columns.length),
    }))
    .filter((one) => one.sections.length),
)

const passthrough = computed(() => ({
  spaceCode: props.spaceCode,
  screen: props.screen,
  disabled: props.disabled,
  isNew: props.isNew,
  // Read off the spec rather than passed in: the screen already knows what it
  // is over, and threading it through every caller would be one more thing to
  // forget on the next form that renders this.
  doctype: props.spec?.doctype || '',
  docname: props.docname,
  // Same argument: the spec carries the doctype's Document States, so a
  // Select's options draw the glyph their badge will draw once chosen.
  states: props.spec?.states || [],
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

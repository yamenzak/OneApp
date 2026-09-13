<template>
  <!--
    A field that is information rather than input — §B5.
  
    The missing third rendering. Everything locked used to be a greyed-out
    control, and a record with twelve of them looks broken rather than
    informational: twelve boxes you cannot type in, several of them still
    showing a placeholder inviting you to.
  
    No box, no grey, no placeholder. The label stays exactly where the
    control's would have been so a form does not reflow as fields lock and
    unlock, and the value is drawn by `FieldCell` — the same component the list
    uses, because "how does a Currency read" is one question and the list
    already answered it for every fieldtype.
  -->
  <div class="flex min-w-0 flex-col gap-1" data-slot="read-value">
    <FieldLabel
      v-if="field.label"
      :label="field.label"
      :icon="field.icon"
      :ai="ai"
      class="text-p-sm text-ink-secondary"
    />
    <!--
      `min-h` matched to a control's text line rather than to a control: a
      read-only field is shorter than the box it replaces, which is the point,
      but a row of them should still sit on a baseline.
    -->
    <div data-slot="read-value-text" class="flex min-h-[1.75rem] min-w-0 items-center">
      <FieldCell
        :column="cell"
        :value="modelValue"
        :row="doc"
        :space-code="spaceCode"
        :screen="screen"
        :states="states"
      />
    </div>
    <p v-if="note" class="text-p-xs text-ink-muted">{{ note }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import FieldCell from '@/modules/onespace/components/screen/bodies/FieldCell.vue'
import FieldLabel from '@/modules/onespace/components/screen/fields/FieldLabel.vue'

const props = defineProps({
  /** The field, as the server describes it — `cell` included. */
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  /** The record, for the cells that read a second value off it. */
  doc: { type: Object, default: () => ({}) },
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
  states: { type: Array, default: () => [] },
  ai: { type: Object, default: null },
  note: { type: String, default: '' },
})

/**
 * The field, as a column.
 *
 * `FieldCell` reads a *column* and the server already puts `cell` on every
 * field — the same answer, computed once in `meta.py`. So this is a rename
 * rather than a second mapping, which is the whole reason the read-only
 * rendering is cheap.
 */
const cell = computed(() => ({
  ...props.field,
  key: props.field.fieldname,
  cell: props.field.cell || 'text',
}))
</script>

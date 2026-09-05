<template>
  <!--
    One change, to a selection.

    Two questions and no more: which field, and what to. Frappe's bulk edit
    asks exactly this and it is the right shape — a dialog that offered several
    fields at once would be a record form applied to forty records, and the
    thing that makes a bulk edit safe is that it is one small, legible change.

    The value is a `FieldControl`, so a Select offers its options and a Link
    opens its picker: the same control the record form draws, which is what
    keeps "set the status" from meaning typing a state nobody declared.
  -->
  <Dialog v-model="showing" :title="`Change ${count} ${count === 1 ? 'record' : 'records'}`">
    <div class="flex flex-col gap-4">
      <Select v-model="chosen" :options="fields" label="Field" placeholder="Which field" />

      <!-- Only once a field is chosen: a control with no field behind it has
           no fieldtype, no options and nothing to validate against. -->
      <div v-if="field" class="flex flex-col gap-1.5">
        <FormLabel :label="field.label" />
        <FieldControl
          v-model="value"
          :field="field"
          :space-code="spaceCode"
          :screen="screen"
          :states="states"
        />
      </div>

      <!-- Said before it happens rather than after. A bulk change is the one
           write in this product with no undo and no per-record confirmation,
           so the sentence names the number and the field. -->
      <p v-if="field" class="text-p-sm text-ink-gray-6">
        {{ count }} {{ count === 1 ? 'record' : 'records' }} will have
        <span class="font-medium text-ink-gray-8">{{ field.label }}</span> set to this.
        Records the doctype refuses — a submitted one, or a rule this value
        breaks — are left alone and named.
      </p>
    </div>

    <template #actions>
      <Button label="Never mind" @click="showing = false" />
      <Button
        variant="solid"
        label="Change them"
        :disabled="!field"
        :loading="working"
        @click="apply"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, FormLabel, Select } from '@/ui'
import FieldControl from '../fields/FieldControl.vue'

const props = defineProps({
  /** Every column the screen could show — the same list the picker offers. */
  columns: { type: Array, default: () => [] },
  /** How many records are selected, for the heading and the sentence. */
  count: { type: Number, default: 0 },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The doctype's Document States, so a Select's options carry their glyphs. */
  states: { type: Array, default: () => [] },
  working: { type: Boolean, default: false },
})

const emit = defineEmits(['apply'])

const showing = defineModel({ type: Boolean, default: false })

const chosen = ref('')
const value = ref(null)

/**
 * The fields a bulk change may set.
 *
 * `editable` is the server's own answer and carries the three questions worth
 * asking — is the fieldtype one a control writes, is the field read-only, and
 * is its permlevel one this person may write. A child table is excluded on top
 * of that: "set this table to that" is not a thing one control can say.
 */
const fields = computed(() =>
  (props.columns || [])
    .filter((one) => one.editable && one.fieldtype !== 'Table')
    .map((one) => ({ label: one.label, value: one.fieldname })),
)

const field = computed(() =>
  (props.columns || []).find((one) => one.fieldname === chosen.value) || null,
)

// A value belongs to the field it was typed for. Keeping it across a change of
// field is how a date ends up in a currency column.
watch(chosen, () => {
  value.value = null
})

// And a dialog opened again starts empty rather than showing the last change
// somebody made, which is a change they might apply twice.
watch(showing, (open) => {
  if (!open) return
  chosen.value = ''
  value.value = null
})

const apply = () => {
  if (!field.value) return
  emit('apply', { field: field.value.fieldname, value: value.value })
}
</script>

<template>
  <!--
    One change, to a selection.

    Two questions and no more: which field, and what to. A dialog that offered
    several fields at once would be a record form applied to forty records, and
    what makes a bulk edit safe is that it is one small, legible change.

    The value is a `FieldControl`, so a Select offers its options and a Link
    opens its picker.
  -->
  <Dialog
    v-model="showing"
    :title="count === 1
      ? __('Change {0} record', [count])
      : __('Change {0} records', [count])"
  >
    <div class="flex flex-col gap-4">
      <Select
        v-model="chosen"
        :options="fields"
        :label="__('Field')"
        :placeholder="__('Which field')"
      />

      <!-- Only once a field is chosen: a control with no field behind it has no
           fieldtype, no options and nothing to validate against. -->
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
           write in this product with no undo, so the sentence names the number
           and the field. -->
      <p v-if="field" class="text-p-sm text-ink-gray-6">
        {{ count === 1
          ? __('One record will have {0} set to this.', [field.label])
          : __('{0} records will have {1} set to this.', [count, field.label]) }}
        {{ __('Any record that refuses the change — a submitted one, or a value a rule forbids — is left alone and named.') }}
      </p>
    </div>

    <template #actions>
      <Button :label="__('Never mind')" @click="showing = false" />
      <Button
        variant="solid"
        :label="__('Change them')"
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
import FieldControl from '@/modules/onespace/components/screen/fields/FieldControl.vue'
import { __ } from '@/shared/lib/runtime/translate'

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
 * The fields a bulk change may set. `editable` is the server's own answer; a
 * child table is excluded on top of that, because "set this table to that" is
 * not a thing one control can say.
 */
const fields = computed(() =>
  (props.columns || [])
    .filter((one) => one.editable && one.fieldtype !== 'Table')
    .map((one) => ({ label: one.label, value: one.fieldname })),
)

const field = computed(() =>
  (props.columns || []).find((one) => one.fieldname === chosen.value) || null,
)

// A value belongs to the field it was typed for: keeping it across a change of
// field is how a date ends up in a currency column.
watch(chosen, () => {
  value.value = null
})

// And a dialog opened again starts empty rather than showing the last change
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

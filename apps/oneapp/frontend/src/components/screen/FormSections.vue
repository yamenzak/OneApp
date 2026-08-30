<template>
  <div class="flex flex-col gap-5">
    <section v-for="(section, index) in sections" :key="index" class="flex flex-col gap-4">
      <!-- A heading only where the doctype wrote one. Frappe's own forms leave
           the first section unlabelled more often than not, and "Details" over
           the first four fields of every record is a word that says nothing. -->
      <h3
        v-if="section.label"
        class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5"
      >
        {{ section.label }}
      </h3>

      <div class="flex flex-col gap-4">
        <!--
          The field's own icon, in a gutter beside the control rather than
          inside its label. Only some of frappe-ui's controls have a `label`
          slot — DatePicker and Duration do not — so putting it there would
          give most fields an icon and silently drop the label from the rest.
          A gutter is uniform, and the control keeps its own label/for pair.
        -->
        <div v-for="field in section.fields" :key="field.fieldname" class="flex gap-2">
          <Icon
            :name="field.icon"
            class="mt-5 size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true"
          />
          <FieldControl
            v-model="values[field.fieldname]"
            :field="field"
            :space-code="spaceCode"
            :screen="screen"
            :disabled="disabled || !field.editable || locked(field)"
            class="min-w-0 flex-1"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { Icon } from '@/ui'
import FieldControl from './FieldControl.vue'

const props = defineProps({
  sections: { type: Array, default: () => [] },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  disabled: { type: Boolean, default: false },
  isNew: { type: Boolean, default: false },
})

// The draft, written into per field. A model rather than a prop: the object is
// the caller's and every control edits one key of it, so passing it down as a
// prop and writing to it is the mutation eslint is right to refuse.
const values = defineModel('values', { type: Object, required: true })

// `set_only_once` is the doctype saying a field is settled at creation. Only
// the record knows whether that has happened, so the flag travels on the field
// and the answer is made here.
const locked = (field) => !!field.set_only_once && !props.isNew
</script>

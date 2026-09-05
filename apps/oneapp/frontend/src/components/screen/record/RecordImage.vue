<template>
  <!--
    The record's own picture, where the doctype declares one — `image_field` is
    Frappe's own answer to "which field is the face of this thing", and the
    desk reads the same one.

    Shown at the head of the details, and replaced in place: an Attach Image
    field would otherwise render as a file box halfway down a form, which is
    where a photograph is least useful.
  -->
  <div class="flex items-center gap-3">
    <Avatar :image="value" :label="label" shape="square" size="3xl" />
    <div v-if="canWrite" class="flex flex-col items-start gap-1">
      <Button
        :label="value ? 'Replace the image' : 'Add an image'"
        @click="picking = true"
      />
      <Button
        v-if="value"
        variant="ghost"
        label="Remove it"
        @click="emit('update:value', '')"
      />
    </div>
    <FilePicker
      v-model="picking"
      kind="Image"
      :attached-to="{ doctype, docname: name, fieldname: field }"
      @picked="(file) => emit('update:value', file.file_url)"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Avatar, Button } from '@/ui'
import FilePicker from '../../drive/FilePicker.vue'

defineProps({
  /** The current image URL, which is what the field holds. */
  value: { type: String, default: '' },
  label: { type: String, default: '' },
  field: { type: String, required: true },
  doctype: { type: String, default: '' },
  name: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})
const emit = defineEmits(['update:value'])

// Whether the picker is open.
const picking = ref(false)
</script>

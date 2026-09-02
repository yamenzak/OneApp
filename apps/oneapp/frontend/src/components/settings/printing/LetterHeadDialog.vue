<template>
  <!--
    A letter head: the paper's own identity, above and below whatever a format
    draws.

    HTML rather than an uploader with three boxes. Frappe's Letter Head takes
    either, and the image path builds an `<img>` and nothing else — no address,
    no company number, no footer — so anyone who wants the second line ends up
    in the HTML anyway. Offering it directly is one control instead of two that
    overwrite each other.
  -->
  <Dialog v-model="showing" :title="name ? `Letter head: ${name}` : 'New letter head'" size="2xl">
    <div class="flex flex-col gap-3">
      <FormControl v-model="label" label="Name" />

      <FormControl
        v-model="values.content"
        type="textarea"
        label="Header"
        :rows="6"
        description="HTML, rendered as a template with the document in scope."
      />

      <FormControl
        v-model="values.footer"
        type="textarea"
        label="Footer"
        :rows="4"
      />

      <div class="flex flex-wrap gap-2">
        <Select v-model="values.align" class="w-40" label="Align" :options="ALIGNMENTS" />
        <Select
          v-model="values.footer_align"
          class="w-40"
          label="Footer align"
          :options="ALIGNMENTS"
        />
      </div>

      <!--
        The image is a path rather than an uploader. Frappe stores it as an
        Attach and builds the header HTML around it — but a letter head that
        has any header HTML at all keeps that instead, so an uploader here
        would be a control that silently does nothing half the time. A path,
        beside the HTML it appears in, says what it is.
      -->
      <FormControl
        v-model="values.image"
        label="Image"
        description="A file path or URL. Referenced from the header above, or used on its own."
      />

      <div class="flex flex-wrap gap-2">
        <FormControl
          v-model="values.image_height"
          type="number"
          class="w-40"
          label="Image height (px)"
        />
        <FormControl
          v-model="values.image_width"
          type="number"
          class="w-40"
          label="Image width (px)"
        />
      </div>

      <div class="flex flex-wrap gap-4">
        <Switch v-model="values.default" label="Use this one by default" />
        <Switch v-model="values.disabled" label="Retired" />
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>

    <template #actions>
      <Button
        variant="solid"
        label="Save"
        :loading="saving"
        :disabled="!label.trim()"
        @click="save"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl, Select, Switch } from '@/ui'
import { workspace } from '../../../lib/workspace'
import { errorText } from '../../../lib/errors'

const ALIGNMENTS = ['Left', 'Center', 'Right'].map((one) => ({ label: one, value: one }))

const EMPTY = {
  content: '',
  footer: '',
  image: '',
  image_height: 0,
  image_width: 0,
  align: 'Left',
  footer_align: 'Left',
  default: false,
  disabled: false,
}

const props = defineProps({
  name: { type: String, default: '' },
})

const emit = defineEmits(['saved'])
const showing = defineModel({ type: Boolean, default: false })

const label = ref('')
const values = reactive({ ...EMPTY })
const saving = ref(false)
const error = ref('')

watch(
  () => [showing.value, props.name],
  async ([open]) => {
    if (!open) return
    error.value = ''
    if (!props.name) {
      label.value = ''
      Object.assign(values, EMPTY)
      return
    }
    try {
      const found = await workspace.letterHead(props.name)
      label.value = found.name
      Object.assign(values, EMPTY, found)
    } catch (raised) {
      error.value = errorText(raised)
    }
  },
  { immediate: true },
)

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await workspace.saveLetterHead(label.value.trim(), { ...values }, props.name)
    emit('saved')
    showing.value = false
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}
</script>

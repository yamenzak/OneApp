<template>
  <!--
    Making a record. A dialog, which is the one place a modal is the right
    answer: there is nothing behind it to refer to yet, the decision is short,
    and cancelling leaves nothing behind. Reading a record is not this.
  -->
  <!-- The screen's own word for one of these, singular: a screen is called
       "Tasks" and "New Tasks" is not a sentence. The screen's rather than the
       doctype's — this used to read **New ToDo** on a screen called Tasks. -->
  <FormDialog
    v-model="open"
    :title="__('New {0}', [spec?.singular || __('record')])"
    size="3xl"
    :dismissible="!dirty"
    :close-label="dirty ? __('Discard and close') : __('Close')"
  >
    <form class="flex flex-col gap-4" @submit.prevent="save()">
      <!-- The doctype's own tabs and sections. See RecordForm. -->
      <RecordForm
        v-model:values="form"
        :spec="spec"
        :space-code="spaceCode"
        :screen="screen"
        is-new
      />
      <ErrorMessage v-if="error" :message="error" />
    </form>

    <template #actions>
      <!--
        Two ways to finish, because one of them is a different intent. Seeding a
        catalogue is a loop, and a dialog that navigates into the record after
        each one turns that into open, fill, save, go back, press New.
      -->
      <Button
        v-if="spec?.can_create"
        :label="__('Create another')"
        :loading="saving === 'another'"
        :disabled="saving !== ''"
        @click="save({ another: true })"
      />
      <Button
        variant="solid"
        :label="__('Create')"
        :loading="saving === 'close'"
        :disabled="saving !== ''"
        @click="save()"
      />
    </template>
  </FormDialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, ErrorMessage } from '@/ui'
import FormDialog from '@/modules/onespace/components/screen/record/FormDialog.vue'
import RecordForm from '@/modules/onespace/components/screen/record/RecordForm.vue'
import { notifySuccess } from '@/shared/lib/runtime/notify'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /**
   * Fields the form opens with already filled in. The board's New sits inside a
   * column and means "a new one, here". Seeded rather than forced: an ordinary
   * value in an ordinary control.
   */
  preset: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'created'])

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const form = reactive({})
const error = ref('')
// Which button is in flight, or ''. Not a boolean: two buttons finish
// differently and only the one that was pressed should show a spinner.
const saving = ref('')

// What was actually filled in, and nothing else.
//
// A null date or a blank Select is a value the column will not take, and comes
// back as an OperationalError with nothing a person can act on. And a doctype's
// `default` is often not a value at all — ToDo's date field defaults to the
// string `Today` — so posting it back writes the word rather than the date.
//
// Both disappear by leaving the field out: Frappe applies its own defaults, on
// the server, where the words mean something.
const filled = () => {
  const values = {}
  for (const [key, value] of Object.entries(form)) {
    if (value === null || value === undefined || value === '') continue
    values[key] = value
  }
  return values
}

// Whether there is anything here worth not losing — what stops the dialog
// vanishing on a stray Escape. Empty, it closes as freely as it ever did.
const dirty = computed(() => Object.keys(filled()).length > 0)

const blank = () => {
  error.value = ''
  Object.keys(form).forEach((key) => delete form[key])
  Object.assign(form, props.preset || {})
}

const save = async ({ another = false } = {}) => {
  if (saving.value) return
  saving.value = another ? 'another' : 'close'
  error.value = ''
  try {
    const made = await workspace.saveRecord(props.spaceCode, props.screen, filled(), null)
    if (another) {
      // Stay, and say so: the dialog looks identical after a successful create
      // and an ignored click.
      notifySuccess(
        __('{0} {1} created', [props.spec?.singular || __('Record'), made?.name || '']),
      )
      blank()
      return
    }
    open.value = false
    // Opened straight away: the point of making one is to be in it.
    emit('created', made?.name || '')
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = ''
  }
}

// A blank form every time it opens — blank being the preset, where there is
// one. A dialog that remembers the last attempt quietly creates a second copy.
watch(open, (showing) => {
  if (showing) blank()
})
</script>

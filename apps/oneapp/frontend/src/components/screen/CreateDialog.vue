<template>
  <!--
    Making a record. A dialog, which is the one place a modal is the right
    answer: there is nothing behind it to refer to yet, the decision is short,
    and cancelling leaves nothing behind. Frappe CRM moved every creation into
    one for the same reason.

    Reading a record is not this — that is a pane beside the list, because a
    record you are reading is a record you are reading *against* the list.
  -->
  <!-- The doctype's own word for one of these, not the screen's: a screen is
       called "Tasks" and "New Tasks" is not a sentence. It is the same label
       the link picker's quick-create uses. -->
  <FormDialog
    v-model="open"
    :title="`New ${spec?.doctype_label || 'record'}`"
    size="3xl"
    :dismissible="!dirty"
    :close-label="dirty ? 'Discard and close' : 'Close'"
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
        Two ways to finish, because one of them is a different intent. Seeding
        a catalogue — four plans, three regions, a handful of add-ons — is a
        loop, and a dialog that closes and navigates into the record after each
        one turns that into open, fill, save, go back, press New.

        Frappe's own quick entry has had this for years, and it is the same
        button: create, keep the dialog, empty the form.
      -->
      <Button
        v-if="spec?.can_create"
        label="Create another"
        :loading="saving === 'another'"
        :disabled="saving !== ''"
        @click="save({ another: true })"
      />
      <Button
        variant="solid"
        label="Create"
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
import FormDialog from './FormDialog.vue'
import RecordForm from './RecordForm.vue'
import { notifySuccess } from '../../lib/notify'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
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
// Two things go wrong when a create posts every field it drew. A null date or
// a blank Select is a value the column will not take, and the answer comes
// back as an OperationalError with nothing a person can act on. And a
// doctype's `default` is often not a value at all — ToDo's date field defaults
// to the string `Today`, and `__user` and `Now` are the same kind of thing —
// so seeding the form with them and posting them back writes the word rather
// than the date.
//
// Both disappear by leaving the field out: Frappe applies its own defaults, on
// the server, where the words mean something. It is what the desk's quick
// entry does too.
const filled = () => {
  const values = {}
  for (const [key, value] of Object.entries(form)) {
    if (value === null || value === undefined || value === '') continue
    values[key] = value
  }
  return values
}

// Whether there is anything here worth not losing.
//
// This is what stops the dialog vanishing on a stray Escape or a click that
// landed outside it. Empty, it closes as freely as it ever did — a dialog you
// opened by mistake should not argue with you.
const dirty = computed(() => Object.keys(filled()).length > 0)

const blank = () => {
  error.value = ''
  Object.keys(form).forEach((key) => delete form[key])
}

const save = async ({ another = false } = {}) => {
  if (saving.value) return
  saving.value = another ? 'another' : 'close'
  error.value = ''
  try {
    const made = await workspace.saveRecord(props.spaceCode, props.screen, filled(), null)
    if (another) {
      // Stay, and say so: the dialog looks identical after a successful create
      // and an ignored click, so without the toast there is no way to tell
      // which one just happened.
      notifySuccess(`${props.spec?.doctype_label || 'Record'} ${made?.name || ''} created`)
      blank()
      return
    }
    open.value = false
    // Opened straight away: the point of making one is to be in it, and a
    // dialog that closes onto a list leaves the person hunting for the row
    // they just created.
    emit('created', made?.name || '')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = ''
  }
}

// A blank form every time it opens. A dialog that remembers the last attempt
// is a dialog that quietly creates a second copy of it.
watch(open, (showing) => {
  if (showing) blank()
})
</script>

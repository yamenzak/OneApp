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
  <Dialog v-model="open" :title="`New ${spec?.doctype_label || 'record'}`" size="3xl">
    <form class="flex flex-col gap-4" @submit.prevent="save">
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
      <Button variant="solid" label="Create" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage } from '@/ui'
import RecordForm from './RecordForm.vue'
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
const saving = ref(false)

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

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    const made = await workspace.saveRecord(props.spaceCode, props.screen, filled(), null)
    open.value = false
    // Opened straight away: the point of making one is to be in it, and a
    // dialog that closes onto a list leaves the person hunting for the row
    // they just created.
    emit('created', made?.name || '')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

// A blank form every time it opens. A dialog that remembers the last attempt
// is a dialog that quietly creates a second copy of it.
watch(open, (showing) => {
  if (!showing) return
  error.value = ''
  Object.keys(form).forEach((key) => delete form[key])
})
</script>

<template>
  <!--
    One event of the reader's own: the only thing the diary stores rather than
    merges. Everything else on that grid is a record under a screen's rules and
    is edited there.

    Four fields, and no more on purpose. A name, when it is, whether it takes
    the whole day, and what it is about. Who else is in it and what reminds you
    are the next piece of this — they are a people picker and an alerts table,
    and neither is a field.
  -->
  <Dialog v-model="open" :title="draft.name ? 'Edit event' : 'New event'">
    <div class="flex flex-col gap-3">
      <FormControl
        v-model="draft.subject"
        label="Name"
        placeholder="Quarterly review"
        data-slot="event-subject"
      />

      <!--
        A whole day first, because it changes what the two below are asking
        for: "which day" rather than "what time".
      -->
      <Switch
        v-model="draft.all_day"
        label="All day"
        description="Which day rather than what time."
        data-slot="event-all-day"
      />

      <component
        :is="draft.all_day ? DatePicker : DateTimePicker"
        v-model="draft.starts_on"
        label="Starts"
        data-slot="event-starts"
      />
      <component
        :is="draft.all_day ? DatePicker : DateTimePicker"
        v-model="draft.ends_on"
        label="Ends"
        description="Leave it empty for a moment rather than a span."
        data-slot="event-ends"
      />

      <Textarea v-model="draft.description" label="Notes" :rows="3" />

      <ErrorMessage v-if="error" :message="error" />
    </div>

    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save()" />
      <!-- Only where there is something to remove. A new event's dialog
           offering Delete is a button that cannot mean anything. -->
      <Button
        v-if="draft.name"
        theme="red"
        variant="subtle"
        label="Delete"
        :loading="removing"
        @click="remove()"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import {
  Button,
  DatePicker,
  DateTimePicker,
  Dialog,
  ErrorMessage,
  FormControl,
  Switch,
  Textarea,
} from '@/ui'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const props = defineProps({
  /** The event being edited, or a date to start a new one on. */
  editing: { type: String, default: '' },
  on: { type: String, default: '' },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['saved'])

const BLANK = { name: '', subject: '', starts_on: '', ends_on: '', all_day: false, description: '' }

const draft = reactive({ ...BLANK })
const error = ref('')
const saving = ref(false)
const removing = ref(false)

/**
 * Filled when the dialog opens, not when the props change.
 *
 * A dialog that reloads under somebody's typing because a prop moved is a
 * dialog that eats what they wrote — and the props here move with the grid
 * behind it.
 */
watch(open, async (showing) => {
  if (!showing) return
  error.value = ''
  Object.assign(draft, BLANK)
  if (props.editing) {
    try {
      Object.assign(draft, await workspace.diaryEvent(props.editing))
      draft.all_day = !!draft.all_day
    } catch (raised) {
      error.value = errorText(raised)
    }
  } else if (props.on) {
    // The day somebody clicked, which is the whole reason clicking a cell is
    // faster than pressing New.
    draft.starts_on = props.on
  }
})

async function save() {
  saving.value = true
  error.value = ''
  try {
    await workspace.saveDiaryEvent({ ...draft })
    open.value = false
    emit('saved')
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

async function remove() {
  removing.value = true
  error.value = ''
  try {
    await workspace.removeDiaryEvent(draft.name)
    open.value = false
    emit('saved')
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    removing.value = false
  }
}
</script>

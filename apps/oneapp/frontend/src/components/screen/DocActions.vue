<template>
  <!--
    What can be done to this record now, as one row of buttons.

    The list arrives from the server already decided — `docflow.state` answers
    with a workflow's transitions or with Submit / Cancel / Amend, in the same
    shape either way. So nothing here asks which mechanism is in play, and the
    day a doctype gains a workflow the header does not change: the buttons say
    "Approve" instead of "Submit" because the server started saying so.

    Frappe's own rule underneath it: a workflow **owns** the transition, so the
    plain Submit is never offered beside one. Two buttons that both submit and
    disagree about who may press them is the failure that rule prevents.
  -->
  <span v-if="actions.length" class="flex shrink-0 items-center gap-1">
    <Badge
      v-if="stateLabel"
      data-slot="doc-state"
      :label="stateLabel"
      :theme="stateTheme"
      variant="subtle"
    />
    <Button
      v-for="one in actions"
      :key="one.action"
      :data-slot="`doc-action-${one.kind}`"
      :variant="one.cancels ? 'subtle' : 'solid'"
      :theme="one.cancels ? 'red' : 'gray'"
      :label="one.action"
      :loading="running === one.action"
      :disabled="Boolean(running) || dirty"
      :tooltip="dirty ? 'Save your changes first' : undefined"
      @click="ask(one)"
    />
  </span>

  <!--
    Anything that cancels asks first. Not everything destructive is called
    Cancel — a workflow's "Reject" may be the transition that unwrites a
    ledger — so the question is the state's own `doc_status` rather than the
    word on the button, which is what the server sends `cancels` for.
  -->
  <Dialog
    v-model="confirming"
    :title="pending?.action || 'Are you sure?'"
  >
    <p class="text-p-base text-ink-gray-7">{{ warning }}</p>
    <template #actions>
      <Button label="Never mind" @click="confirming = false" />
      <Button variant="solid" theme="red" :label="pending?.action" @click="run(pending)" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Dialog } from '@/ui'
import { workspace } from '../../lib/workspace'
import { notifyError } from '../../lib/notify'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  // `_state` off the record: docstatus, the workflow's state, and what may be
  // done next. Absent on a doctype that is neither submittable nor governed by
  // a workflow, which is most of them.
  state: { type: Object, default: null },
  // Which field the screen already badges beside the record's name. A screen
  // whose `status_field` *is* the workflow's state field is already saying
  // where this stands, and saying it twice in two places is how a header
  // starts to read as a debug view.
  statusField: { type: String, default: '' },
  // Unsaved edits. Submitting what is on the server while the form holds
  // something else is the one way to submit a document nobody has read.
  dirty: { type: Boolean, default: false },
})

const emit = defineEmits(['moved', 'opened'])

const running = ref('')
const confirming = ref(false)
const pending = ref(null)

const actions = computed(() => props.state?.actions || [])

// The workflow's state where there is one, and the docstatus where there is
// not. Never both: a workflow state carries the docstatus, so showing "Pending
// Approval" beside "Draft" is saying one thing twice in two vocabularies.
const stateLabel = computed(() => {
  const flow = props.state?.workflow
  if (flow) return flow.state_field === props.statusField ? '' : flow.state
  return props.state?.status || ''
})
const stateTheme = computed(() => props.state?.workflow?.theme || 'gray')

const warning = computed(() =>
  props.state?.workflow
    ? `This takes the record to ${pending.value?.next || 'the next state'}, which cancels it.`
    : 'Cancelling unwinds what submitting this wrote. It cannot be undone.',
)

const ask = (one) => {
  if (!one.cancels) return run(one)
  pending.value = one
  confirming.value = true
}

const run = async (one) => {
  if (!one) return
  confirming.value = false
  running.value = one.action
  try {
    if (one.kind === 'workflow') {
      emit('moved', await workspace.workflowAction(props.spaceCode, props.screen, props.name, one.action))
    } else if (one.kind === 'amend') {
      // The answer to "amend this" is a different record, so the pane follows
      // it rather than redrawing the cancelled one.
      const made = await workspace.amend(props.spaceCode, props.screen, props.name)
      emit('opened', made?.name)
    } else {
      emit('moved', await workspace[one.kind](props.spaceCode, props.screen, props.name))
    }
  } catch (raised) {
    notifyError(raised.message || String(raised))
  } finally {
    running.value = ''
    pending.value = null
  }
}
</script>

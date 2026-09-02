<template>
  <!--
    What can be done to this record now.

    The list arrives from the server already decided — `docflow.state` answers
    with a workflow's transitions or with Submit / Cancel / Amend, in the same
    shape either way. So nothing here asks which mechanism is in play, and the
    day a doctype gains a workflow the header does not change: the buttons say
    "Approve" instead of "Submit" because the server started saying so.

    Frappe's own rule underneath it: a workflow **owns** the transition, so the
    plain Submit is never offered beside one. Two buttons that both submit and
    disagree about who may press them is the failure that rule prevents.

    Three rules shape the row, and none of them names an action:

    * **A step forward is a button; a step that cancels is in the menu.** A
      submitted document's only plain action is Cancel, so a submitted document
      is three dots and nothing else — which is the point: unwinding a ledger
      entry is not something to leave one mis-click away from the thing you
      came here to do.
    * **The first step forward is the green one**, and the only solid one. It
      is what the record is waiting for; anything beside it is an alternative
      and is drawn as one. Two solid buttons is two primaries, which is none.
    * **Nothing at all while the form is dirty.** Save is in this same place
      then. Submitting what is on the server while the form holds something
      else is how a document gets submitted that nobody has read, and a
      disabled button with an explanation is a worse way to say so than not
      offering the thing that is not the next step.

    What is *not* here any more: the badge saying where the record stands. That
    is not an action, and it was a screen-width from the record's name — the
    place people already read a status. It sits beside the name now, with the
    doctype's own status field, drawn by the same component.
  -->
  <span v-if="actions.length && !dirty" class="flex shrink-0 items-center gap-1">
    <Button
      v-for="(one, at) in forward"
      :key="one.action"
      :data-slot="`doc-action-${one.kind}`"
      :variant="at === 0 ? 'solid' : 'subtle'"
      :theme="at === 0 ? 'green' : 'gray'"
      :label="one.action"
      :loading="running === one.action"
      :disabled="Boolean(running)"
      @click="ask(one)"
    />

    <Dropdown v-if="undoing.length" :options="menu" align="end">
      <Button
        data-slot="doc-more"
        icon="lucide-more-vertical"
        variant="ghost"
        label="What else can be done to this"
        tooltip="More"
        :loading="Boolean(running) && !forward.some((one) => one.action === running)"
      />
    </Dropdown>
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
import { Button, Dialog, Dropdown } from '@/ui'
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
  // Unsaved edits, which put Save in this slot instead.
  dirty: { type: Boolean, default: false },
})

const emit = defineEmits(['moved', 'opened'])

const running = ref('')
const confirming = ref(false)
const pending = ref(null)

const actions = computed(() => props.state?.actions || [])

// The split the whole row turns on, and it is the server's answer rather than
// this file's reading of a label: `cancels` is true where the next state
// carries docstatus 2.
const forward = computed(() => actions.value.filter((one) => !one.cancels))
const undoing = computed(() => actions.value.filter((one) => one.cancels))

const menu = computed(() =>
  undoing.value.map((one) => ({
    label: one.action,
    icon: 'lucide-undo-2',
    theme: 'red',
    onClick: () => ask(one),
  })),
)

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

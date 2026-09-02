<template>
  <!--
    Everything you can do to this record that is not editing one of its fields,
    as one primary button and one menu.

    It was eight controls in a row: the screen's actions, assign, like, the
    document's steps, print, follow, Save, close. Every one of them defensible
    on its own and together a toolbar you read rather than use — and the two
    that matter, the next step and Save, were the hardest to find in it because
    nothing said they were different from the rest.

    So: **one button, and everything else behind three dots.** The button is
    the step the record is waiting for. The menu is the rest, in the order
    somebody would look for it, with the steps that unwind a document last and
    in red.

    Where the list comes from does not show. `docflow.state` answers with a
    workflow's transitions or with Submit / Cancel / Amend in the same shape
    either way, so the day a doctype gains a workflow the header does not
    change: the button says "Approve" instead of "Submit" because the server
    started saying so. Frappe's own rule underneath it — a workflow **owns**
    the transition, so the plain Submit is never offered beside one.

    Two rules decide what goes where, and neither names an action:

    * **A step forward is the button; a step that cancels is in the menu**, in
      red, and asks before it runs. Which is which comes off the next state's
      own `doc_status`, never the word on it — "Reject" and "Return to draft"
      are the same word to a reader and different things to the ledger. So a
      submitted document is three dots and nothing else: unwinding a ledger
      entry should not sit where the eye has just learned to click.
    * **Nothing at all while the form is dirty.** Save is in this same place
      then. Submitting what is on the server while the form holds something
      else is how a document gets submitted that nobody has read.

    What is *not* here: assignment, which the Meta tab already offers one tab
    away and which was in the header twice; and the badge saying where the
    record stands, which is not an action and now sits beside the record's
    name, where a status is read.
  -->
  <span v-if="forward.length || menu.length" class="flex shrink-0 items-center gap-1">
    <template v-if="!dirty">
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
    </template>

    <Dropdown v-if="menu.length" :options="menu" align="end">
      <Button
        data-slot="record-more"
        icon="lucide-ellipsis-vertical"
        variant="ghost"
        label="More for this record"
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
  // a workflow, which is most of them — and those still get a menu, because
  // printing and following a note are things you do to a record too.
  state: { type: Object, default: null },
  /**
   * The verbs that are not the framework's: print, follow, like — whatever the
   * record's own header can offer. Handed in rather than known here, because
   * each of them belongs to something this component has no business holding
   * (a dialog, a subscription, a count), and all this needs is a label, a
   * glyph and something to call.
   */
  extras: { type: Array, default: () => [] },
  // Unsaved edits, which put Save in this slot instead.
  dirty: { type: Boolean, default: false },
})

const emit = defineEmits(['moved', 'opened'])

const running = ref('')
const confirming = ref(false)
const pending = ref(null)

const actions = computed(() => props.state?.actions || [])

// The split the row turns on, and it is the server's answer rather than this
// file's reading of a label: `cancels` is true where the next state carries
// docstatus 2.
const forward = computed(() => actions.value.filter((one) => !one.cancels))
const undoing = computed(() => (props.dirty ? [] : actions.value.filter((one) => one.cancels)))

// The extras first, because they are what somebody opens this menu for; the
// steps that unwind the document last and in red, because a menu is read top
// down and the thing you rarely mean should not be the thing under the cursor.
const menu = computed(() => [
  ...props.extras.map((one) => ({
    label: one.label,
    icon: one.icon,
    onClick: one.onClick,
  })),
  ...undoing.value.map((one) => ({
    label: one.action,
    icon: 'lucide-undo-2',
    theme: 'red',
    onClick: () => ask(one),
  })),
])

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

<template>
  <!--
    Everything you can do to this record that is not editing one of its fields,
    as one primary button and one menu.

    It was eight controls in a row, and the two that matter — the next step and
    Save — were the hardest to find because nothing said they were different.
    So: **one button, and everything else behind three dots.**

    Where the list comes from does not show. `docflow.state` answers with a
    workflow's transitions or with Submit / Cancel / Amend in the same shape, so
    the day a doctype gains a workflow the header does not change.

    Two rules decide what goes where, and neither names an action:

    * **A step forward is the button; a step that cancels is in the menu**, in
      red, and asks first. Which is which comes off the next state's own
      `doc_status`, never the word on it — "Reject" and "Return to draft" are
      the same word to a reader and different things to the ledger.
    * **Nothing at all while the form is dirty.** Save is in this place then:
      submitting what is on the server while the form holds something else is
      how a document gets submitted that nobody has read.
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
        :label="__('More for this record')"
        :tooltip="__('More')"
        :loading="Boolean(running) && !forward.some((one) => one.action === running)"
      />
    </Dropdown>
  </span>

  <!--
    Anything that cancels asks first. Not everything destructive is called
    Cancel — a workflow's "Reject" may be the transition that unwrites a ledger
    — so the question is the state's own `doc_status`.
  -->
  <Dialog
    v-model="confirming"
    :title="pending?.action || __('Cancel this record')"
  >
    <p class="text-p-base text-ink-gray-7">{{ warning }}</p>
    <template #actions>
      <Button :label="__('Never mind')" @click="confirming = false" />
      <Button variant="solid" theme="red" :label="pending?.action" @click="run(pending)" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, Dropdown } from '@/ui'
import { workspace } from '@/shared/lib/workspace'
import { notifyError } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  // `_state` off the record: docstatus, the workflow's state, and what may be
  // done next. Absent on a doctype that is neither submittable nor governed by
  // a workflow, which still gets a menu.
  state: { type: Object, default: null },
  /**
   * The verbs that are not the framework's: print, follow, like. Handed in
   * rather than known here, because each belongs to something this component
   * has no business holding — all it needs is a label, a glyph and a call.
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

// The extras first, because they are what somebody opens this menu for; then
// the steps that unwind the document; and last whatever destroys it.
//
// `theme` is carried rather than dropped: an extra may be destructive — Delete
// is — and a red entry sitting among the ordinary ones is one somebody presses
// by accident. Sorting on it here rather than asking each caller to know where
// in the list it belongs.
const ordinary = computed(() => props.extras.filter((one) => one.theme !== 'red'))
const destroying = computed(() => props.extras.filter((one) => one.theme === 'red'))

const entry = (one) => ({
  label: one.label,
  icon: one.icon,
  ...(one.theme ? { theme: one.theme } : {}),
  onClick: one.onClick,
})

const menu = computed(() => [
  ...ordinary.value.map(entry),
  ...undoing.value.map((one) => ({
    label: one.action,
    icon: 'lucide-undo-2',
    theme: 'red',
    onClick: () => ask(one),
  })),
  ...destroying.value.map(entry),
])

const warning = computed(() =>
  props.state?.workflow
    ? __('This takes the record to {0}, which cancels it.', [
      pending.value?.next || __('the next state'),
    ])
    : __('Cancelling unwinds what submitting this wrote. It cannot be undone.'),
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
    notifyError(raised)
  } finally {
    running.value = ''
    pending.value = null
  }
}
</script>

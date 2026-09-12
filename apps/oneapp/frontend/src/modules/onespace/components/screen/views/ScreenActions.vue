<template>
  <!--
    What a screen can do to a record that is not editing one of its fields.

    Declared by the space, resolved server-side, and rendered the same way
    wherever it appears: one button when there is one, a menu when there are
    more, so a screen with a single action does not hide it behind a chevron.

    An action either calls a method or opens another screen with this record in
    the address — the resolver refuses a declaration that means to do both, so
    this only has to render whichever one it is.

    **Every action is rendered in both places.** `scope` says how many records
    a verb takes, not where its button lives — it used to mean the second
    thing, which left half the actions unreachable from the open record and
    half unreachable from a selection, and made "where is the button" a
    question about somebody's declaration. A verb that only takes one record
    is still offered in the selection bar; it is disabled until exactly one
    row is ticked, and says so.

    A method action may also declare `upload`, which is a modifier rather than
    a third kind: the button opens a file picker first, the file becomes a
    private `File`, and its url is the one extra argument the run carries.
  -->
  <!-- The picker itself. A hidden input rather than `FileUploader`, for the
       reason `Drive.vue` gives: the upload belongs to the action being run,
       not to a component with reactive state of its own. -->
  <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
  <input
    ref="chooser"
    name="screen-action-upload"
    type="file"
    class="hidden"
    @change="chosenFile"
  >

  <template v-if="!items.length" />

  <Button
    v-else-if="items.length === 1"
    :icon-left="items[0].icon"
    :label="items[0].label"
    :loading="running === items[0].key"
    :disabled="!ready(items[0])"
    :tooltip="reason(items[0])"
    variant="subtle"
    @click="choose(items[0])"
  />

  <Dropdown v-else :options="options">
    <Button
      icon-right="lucide-chevron-down"
      :label="__('Actions')"
      variant="subtle"
      :loading="Boolean(running)"
    />
  </Dropdown>

  <!--
    Anything that cannot be undone from here says so before it runs. Which ones
    those are is the declaration's call, not this component's: it renders a
    confirmation exactly when the action carries the sentence to put in it.
  -->
  <Dialog v-model="confirming" :title="pending?.label || ''">
    <p class="text-p-base text-ink-secondary">{{ pending?.confirm }}</p>
    <template #actions>
      <Button
        variant="solid"
        :label="pending?.label"
        :loading="Boolean(running)"
        @click="run(pending)"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, Dropdown } from '@/ui'
import { putFile } from '@/modules/onestorage/lib/attach'
import { callMethod } from '@/shared/lib/runtime/resource'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The screen's declared actions, as the resolver returned them. */
  actions: { type: Array, default: () => [] },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Which records this is being run against. */
  names: { type: Array, default: () => [] },
})

const emit = defineEmits(['ran'])

const router = useRouter()
const running = ref('')
const confirming = ref(false)
const pending = ref(null)
const chooser = ref(null)
// Which action the open picker belongs to. The picker is one element shared by
// every upload action on the screen, so the choice has to be remembered across
// the click that opens it and the change that answers.
const awaiting = ref(null)

// Every declared action, wherever this is being rendered. The filtering this
// used to do is the inconsistency it now avoids.
const items = computed(() => props.actions || [])

/** Whether this verb can run against what is currently chosen. */
function ready(action) {
  if (!props.names.length) return false
  return (action.scope || 'one') === 'many' || props.names.length === 1
}

/** Why not, in the tooltip, rather than a button that does nothing. */
function reason(action) {
  if (!props.names.length) return __('Choose a record first.')
  if (!ready(action)) return __('This one runs on a single record at a time.')
  return action.label
}

const options = computed(() =>
  items.value.map((action) => ({
    label: action.label,
    icon: action.icon,
    disabled: !ready(action),
    onClick: () => choose(action),
  })),
)

function choose(action) {
  if (!ready(action)) return
  if (action.upload) {
    // Ask for the file before anything else: a confirmation about a delivery
    // nobody has chosen yet is a question without a subject.
    awaiting.value = action
    chooser.value.value = ''
    chooser.value.click()
    return
  }
  if (action.confirm) {
    pending.value = action
    confirming.value = true
    return
  }
  run(action)
}

async function chosenFile(event) {
  const file = event.target.files?.[0]
  const action = awaiting.value
  awaiting.value = null
  if (!file || !action) return

  running.value = action.key
  try {
    // Private, and not attached to the record: `load_feed` re-files it against
    // the delivery it becomes, so attaching it here would leave a second copy
    // hanging off the source for ever.
    const made = await putFile(file)
    await run(action, made?.file_url)
    notifySuccess(__('{0} delivered.').format(file.name))
  } catch (raised) {
    notifyError(raised)
  } finally {
    running.value = ''
  }
}

async function run(action, fileUrl = '') {
  if (!action) return
  running.value = action.key

  try {
    if (action.screen) {
      // A screen action is navigation, not a call. The record travels as a
      // query parameter the target screen reads, so the result is a link
      // somebody can send rather than a state only clicking reaches.
      confirming.value = false
      // Same space, different screen: the path names the space and the query
      // names the screen, so this is a query change and not a route change.
      await router.push({
        query: { screen: action.screen, [action.param || 'record']: props.names[0] },
      })
      return
    }

    await callMethod('oneapp.onespace.spaceview.run_action', {
      space_code: props.spaceCode,
      screen: props.screen,
      action: action.key,
      name: props.names,
      // Only an action that declared `upload` may carry one, and the server
      // checks that rather than trusting the body — `spaceview/run.py`.
      ...(fileUrl ? { file_url: fileUrl } : {}),
    })
    confirming.value = false
    emit('ran', action)
  } finally {
    running.value = ''
  }
}
</script>

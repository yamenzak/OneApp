<template>
  <!--
    What a screen can do to a record that is not editing one of its fields.

    Declared by the space, resolved server-side, and rendered the same way
    wherever it appears: one button when there is one, a menu when there are
    more, so a screen with a single action does not hide it behind a chevron.

    An action either calls a method or opens another screen with this record in
    the address — the resolver refuses a declaration that means to do both, so
    this only has to render whichever one it is.
  -->
  <template v-if="!items.length" />

  <Button
    v-else-if="items.length === 1"
    :icon-left="items[0].icon"
    :label="items[0].label"
    :loading="running === items[0].key"
    variant="subtle"
    @click="choose(items[0])"
  />

  <Dropdown v-else :options="options">
    <Button
      icon-right="lucide-chevron-down"
      label="Actions"
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
    <p class="text-p-base text-ink-gray-7">{{ pending?.confirm }}</p>
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
import { callMethod } from '../../../lib/resource'

const props = defineProps({
  /** The screen's declared actions, as the resolver returned them. */
  actions: { type: Array, default: () => [] },
  /** `record` beside an open record, `selection` in the selection bar. */
  scope: { type: String, default: 'record' },
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

const items = computed(() =>
  (props.actions || []).filter((action) => (action.scope || 'record') === props.scope),
)

const options = computed(() =>
  items.value.map((action) => ({
    label: action.label,
    icon: action.icon,
    onClick: () => choose(action),
  })),
)

function choose(action) {
  if (!props.names.length) return
  if (action.confirm) {
    pending.value = action
    confirming.value = true
    return
  }
  run(action)
}

async function run(action) {
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

    await callMethod('oneapp.oneapp_core.spaceview.run_action', {
      space_code: props.spaceCode,
      screen: props.screen,
      action: action.key,
      name: props.names,
    })
    confirming.value = false
    emit('ran', action)
  } finally {
    running.value = ''
  }
}
</script>

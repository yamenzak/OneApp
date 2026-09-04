<template>
  <!--
    Who this record is assigned to, and the way to change it.

    Frappe's own model, unchanged: `_assign` is a list of user ids on the
    document, and a ToDo sits beside each one so the record turns up in that
    person's own list rather than only on their avatar. Both halves are the
    server's; this sends a set of people and draws what came back.

    A stack of faces rather than a labelled field, because assignment is not a
    field: it is not on the doctype, it is not in the form, and there is no
    column for it. It is a thing you do to a record, so it sits with the other
    things you do to a record.
  -->
  <MultiSelect
    :model-value="chosen"
    v-model:query="query"
    :options="options"
    :loading="loading"
    :filterable="false"
    :disabled="disabled"
    placeholder="Assign to"
    empty-text="Nobody by that name"
    align="end"
    @update:model-value="write"
    @update:open="opened"
  >
    <!--
      The faces are the control. An empty one still has to be pressable, so it
      falls back to the outline of a person — the same affordance the desk's
      own assignment button uses.
    -->
    <template #trigger>
      <!-- The accessible name is the button's, not MultiSelect's `label`:
           that renders a visible label above the control, and this control's
           whole point is that it is a row of faces. -->
      <Button
        variant="ghost"
        :disabled="disabled"
        aria-label="Assigned to"
        data-slot="assign"
      >
        <span class="flex items-center gap-1.5">
          <AvatarStack v-if="people.length" :people="people" />
          <Icon v-else name="lucide-user-round-plus" class="size-4 text-ink-gray-5" />
        </span>
      </Button>
    </template>

    <!-- Each row is a person, drawn the way every identity here is drawn. -->
    <template #item-prefix="{ item }">
      <Avatar :image="item.image" :label="item.label" shape="circle" size="sm" />
    </template>

    <!-- No footer. MultiSelect offers Select All there, and "assign this to
         everybody in the workspace" is not a thing anybody means to press. -->
    <template #footer><span /></template>
  </MultiSelect>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Avatar, Button, Icon, MultiSelect } from '@/ui'
import AvatarStack from './AvatarStack.vue'
import { workspace } from '../../../lib/workspace'
import { notifyError } from '../../../lib/notify'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  /** `[{ value, label, image }]` — resolved by the server, not ids. */
  people: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['assigned'])

const query = ref('')
const loading = ref(false)
// Who could be assigned. Fetched on the first open rather than with the
// record: a workspace's user list is not part of reading one row, and most
// records are read without anybody touching this.
const offered = ref([])

const chosen = computed(() => props.people.map((one) => one.value))

// The people already on the record, first and always — a search that does not
// match somebody's name would otherwise drop them out of the list and read as
// having unassigned them.
const options = computed(() => {
  const seen = new Set()
  return [...props.people, ...offered.value]
    .filter((one) => !seen.has(one.value) && seen.add(one.value))
    .map((one) => ({ value: one.value, label: one.label, image: one.image }))
})

const load = async () => {
  loading.value = true
  try {
    offered.value = (await workspace.assignees(props.spaceCode, props.screen, query.value)) || []
  } finally {
    loading.value = false
  }
}

const opened = (open) => {
  if (open) load()
}

const write = async (users) => {
  try {
    const after = await workspace.assign(props.spaceCode, props.screen, props.name, users)
    // What the document ended up holding, not what was asked for: an id Frappe
    // refused leaves the two different, and a control that shows the request
    // rather than the result is a control that lies.
    emit('assigned', after?.assigned || [])
  } catch (e) {
    notifyError(e.message || String(e))
  }
}
</script>

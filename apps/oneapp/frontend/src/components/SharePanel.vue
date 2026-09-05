<!--
  Who else can see this thing.

  The body of the share dialog, with no idea what it is sharing. Frappe's
  `DocShare` is a row over `(doctype, name)` and says nothing about what sort of
  document that is, so the *screen* for it should not either — a record and a
  file are shared by the same three questions, and two components would be two
  places to fix "can edit" in.

  What varies is three calls, and they arrive as functions: `offer` (who could
  this go to), `save` and `remove`. The parent owns the endpoint; this owns the
  shape of the conversation.

  Three levels, not four checkboxes. "Can view / Can edit / Can share" are
  questions a person can answer about a colleague; `submit` is a question about
  a document's state that only means anything on some doctypes, and putting it
  in the same list makes the other three harder to read.
-->
<template>
  <div class="flex flex-col gap-4">
    <!--
      Adding somebody. A picker and a level, then Share — rather than adding at
      a default level and making the person go back and change it, which is how
      something ends up shared wider than anybody meant.
    -->
    <div v-if="canShare" class="flex items-end gap-2">
      <Combobox
        v-model="picked"
        v-model:query="query"
        class="min-w-0 flex-1"
        :options="offered"
        :loading="looking"
        :filterable="false"
        label="Who"
        placeholder="Somebody on this workspace"
        empty-text="Nobody by that name"
        @update:open="opened"
      >
        <template #item-prefix="{ item }">
          <Avatar :image="item.image" :label="item.label" shape="circle" size="sm" />
        </template>
      </Combobox>
      <Select v-model="level" label="Access" :options="LEVELS" class="w-40" />
      <Button
        variant="solid"
        label="Share"
        :loading="saving"
        :disabled="!picked"
        @click="add"
      />
    </div>

    <ErrorMessage v-if="error" :message="error" />

    <!-- Who it is with. Each row's level is editable in place, because "they
         should only be able to read this" is the correction people actually
         want to make, and re-sharing to change it is not one. -->
    <ul v-if="people.length" class="flex flex-col">
      <li
        v-for="person in people"
        :key="person.value"
        data-slot="share-row"
        class="flex items-center gap-2 border-b border-outline-gray-1 py-2 last:border-0"
      >
        <Avatar :image="person.image" :label="person.label" shape="circle" size="sm" />
        <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">
          {{ person.label }}
        </span>
        <Select
          :model-value="person.level"
          :options="LEVELS"
          :disabled="!canShare"
          class="w-36"
          @update:model-value="(value) => change(person, value)"
        />
        <Button
          v-if="canShare"
          variant="ghost"
          icon="lucide-x"
          :label="`Stop sharing with ${person.label}`"
          :tooltip="`Stop sharing with ${person.label}`"
          @click="drop(person)"
        />
      </li>
    </ul>

    <EmptyState
      v-else-if="!everyone"
      class="!py-6"
      icon="lucide-share-2"
      title="Not shared"
      :description="emptyText"
    />

    <!--
      Everyone is its own statement rather than a person in the list —
      "anybody who can sign in here" — and drawing it among colleagues is how
      somebody grants it by accident.
    -->
    <div class="flex items-start gap-3 border-t border-outline-gray-1 pt-3">
      <Switch
        :model-value="!!everyone"
        :disabled="!canShare || saving"
        label="Everyone on this workspace"
        description="Anybody who can sign in here, whatever their role reaches."
        @update:model-value="all"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  Avatar,
  Button,
  Combobox,
  ErrorMessage,
  Select,
  Switch,
} from '@/ui'
import EmptyState from './EmptyState.vue'
import { errorText } from '../lib/errors'

// In the order they give things away, which is the order to read them in.
const LEVELS = [
  { label: 'Can view', value: 'read' },
  { label: 'Can edit', value: 'write' },
  { label: 'Can share', value: 'share' },
]

const props = defineProps({
  people: { type: Array, default: () => [] },
  everyone: { type: Object, default: null },
  canShare: { type: Boolean, default: false },
  // What "not shared" means here, which is the one sentence that differs
  // between a record and a file.
  emptyText: {
    type: String,
    default: 'Only people whose role already reaches this can see it.',
  },
  /** async (query) => [{ value, label, image }] */
  offer: { type: Function, required: true },
  /** async ({ user, everyone, level }) => the shares as they now stand */
  save: { type: Function, required: true },
  /** async ({ user, everyone }) => the shares as they now stand */
  remove: { type: Function, required: true },
})

const emit = defineEmits(['shared'])

const saving = ref(false)
const looking = ref(false)
const error = ref('')
const query = ref('')
const picked = ref(null)
const level = ref('read')
const offered = ref([])

const opened = async (isOpen) => {
  if (!isOpen) return
  looking.value = true
  try {
    offered.value = (await props.offer(query.value)) || []
  } finally {
    looking.value = false
  }
}

/** Every write answers with the shares as they stand, re-read on the server. */
const run = async (work) => {
  saving.value = true
  error.value = ''
  try {
    emit('shared', await work())
    picked.value = null
    query.value = ''
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

const add = () =>
  run(() => props.save({ user: picked.value?.value || picked.value, level: level.value }))

const change = (person, value) => run(() => props.save({ user: person.value, level: value }))

const drop = (person) => run(() => props.remove({ user: person.value }))

const all = (on) =>
  run(() => (on ? props.save({ everyone: 1, level: 'read' }) : props.remove({ everyone: 1 })))

/** So a parent that opens this in a dialog can prime the picker. */
defineExpose({ reset: () => { error.value = ''; picked.value = null; level.value = 'read' } })
</script>

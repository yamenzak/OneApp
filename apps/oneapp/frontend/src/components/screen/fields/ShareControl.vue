<template>
  <!--
    Who else can see this record.

    Frappe's `DocShare`, and the reason to use it rather than invent something
    is what reads it: the framework folds shares into the permission condition
    of every list query, so a record shared with somebody becomes visible to
    them with nothing written anywhere else.

    Three levels, not four checkboxes. "Can view / Can edit / Can share" are
    questions a person can answer about a colleague; `submit` is a question
    about a document's state that only means anything on some doctypes, and
    putting it in the same list makes the other three harder to read.
  -->
  <span>
    <Button
      variant="ghost"
      data-slot="share"
      :aria-label="summary"
      @click="open()"
    >
      <span class="flex items-center gap-1.5">
        <AvatarStack v-if="people.length" :people="people" />
        <Badge
          v-else-if="everyone"
          label="Everyone"
          theme="blue"
          variant="subtle"
        />
        <Icon v-else name="lucide-plus" class="size-4 text-ink-gray-5" />
      </span>
    </Button>

    <Dialog v-model="showing" title="Share this record">
      <div class="flex flex-col gap-4">
        <!--
          Adding somebody. A picker and a level, then Share — rather than
          adding at a default level and making the person go back and change
          it, which is how a record ends up shared wider than anybody meant.
        -->
        <div v-if="canShare" class="flex items-end gap-2">
          <Combobox
            class="min-w-0 flex-1"
            v-model="picked"
            v-model:query="query"
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

        <!-- Who it is with. Each row's level is editable in place, because
             "they should only be able to read this" is the correction people
             actually want to make and re-sharing to change it is not one. -->
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
          description="Only people whose role already reaches this record can see it."
        />

        <!--
          Everyone is its own statement rather than a person in the list —
          "anybody who can sign in here" — and drawing it among colleagues is
          how somebody grants it by accident.
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
    </Dialog>
  </span>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Combobox,
  Avatar,
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  Icon,
  Select,
  Switch,
} from '@/ui'
import AvatarStack from './AvatarStack.vue'
import EmptyState from '../../EmptyState.vue'
import { workspace } from '../../../lib/workspace'
import { errorText } from '../../../lib/errors'

// In the order they give things away, which is the order to read them in.
const LEVELS = [
  { label: 'Can view', value: 'read' },
  { label: 'Can edit', value: 'write' },
  { label: 'Can share', value: 'share' },
]

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  people: { type: Array, default: () => [] },
  everyone: { type: Object, default: null },
  canShare: { type: Boolean, default: false },
})

const emit = defineEmits(['shared'])

const showing = ref(false)
const saving = ref(false)
const looking = ref(false)
const error = ref('')
const query = ref('')
const picked = ref(null)
const level = ref('read')
const offered = ref([])

const summary = computed(() => {
  if (props.everyone) return 'Shared with everyone on this workspace'
  if (props.people.length) {
    return `Shared with ${props.people.map((one) => one.label).join(', ')}`
  }
  return 'Share this record'
})

const open = () => {
  error.value = ''
  picked.value = null
  level.value = 'read'
  showing.value = true
}

const opened = async (isOpen) => {
  if (!isOpen) return
  looking.value = true
  try {
    offered.value =
      (await workspace.shareable(props.spaceCode, props.screen, query.value)) || []
  } finally {
    looking.value = false
  }
}

/** Every write answers with the shares as they stand, re-read on the server. */
const settled = (result) => {
  emit('shared', result)
  picked.value = null
  query.value = ''
}

const run = async (work) => {
  saving.value = true
  error.value = ''
  try {
    settled(await work())
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

const add = () =>
  run(() =>
    workspace.setShare(props.spaceCode, props.screen, props.name, {
      user: picked.value?.value || picked.value,
      level: level.value,
    }),
  )

const change = (person, value) =>
  run(() =>
    workspace.setShare(props.spaceCode, props.screen, props.name, {
      user: person.value,
      level: value,
    }),
  )

const drop = (person) =>
  run(() =>
    workspace.unshare(props.spaceCode, props.screen, props.name, { user: person.value }),
  )

const all = (on) =>
  run(() =>
    on
      ? workspace.setShare(props.spaceCode, props.screen, props.name, {
          everyone: 1,
          level: 'read',
        })
      : workspace.unshare(props.spaceCode, props.screen, props.name, { everyone: 1 }),
  )
</script>

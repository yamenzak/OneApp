<template>
  <!--
    What the record *is*, and who else is on it.

    The desk's own sidebar, and its shape is the argument: the record's face and
    name, then the four things you do to a record *about other people* — assign
    it, file something against it, tag it, share it — then who made it and when.

    One row shape throughout: a glyph, a label, and the current answer pressed
    to the right, so the column of values lands on the same x whatever the row
    is.
  -->
  <div class="flex flex-col pt-4">
    <!-- The record, once: its face and its name. -->
    <div class="flex items-center gap-3 pb-4">
      <Avatar :image="image" :label="label" shape="square" size="3xl" />
      <div class="flex min-w-0 flex-col gap-0.5">
        <p class="truncate text-base font-medium text-ink-gray-8">{{ label }}</p>
        <p v-if="record.name !== label" class="truncate font-mono text-p-xs text-ink-gray-5">
          {{ record.name }}
        </p>
        <div v-if="imageField && canWrite" class="-ms-2 mt-1 flex items-center">
          <Button
            variant="ghost"
            size="sm"
            :label="image ? __('Change picture') : __('Add a picture')"
            @click="picking = true"
          />
          <Button
            v-if="image"
            variant="ghost"
            size="sm"
            icon="lucide-trash-2"
            :label="__('Remove the picture')"
            :tooltip="__('Remove the picture')"
            @click="emit('update:image', '')"
          />
        </div>
        <!-- A picture the workspace already has is the commonest case here, and
             before the picker the only way to reuse one was to upload it
             again. -->
        <FilePicker
          v-model="picking"
          kind="Image"
          :attached-to="{ doctype, docname: record.name, fieldname: imageField }"
          @picked="(file) => emit('update:image', file.file_url)"
        />
      </div>
    </div>

    <!-- The four. Each is a control the record already has elsewhere; this is
         where they are all in one place. -->
    <ul class="flex flex-col border-y border-outline-gray-1 py-1">
      <li class="flex min-h-9 items-center gap-2">
        <Icon name="lucide-users" class="size-4 shrink-0 text-ink-gray-5" />
        <span class="flex-1 text-p-sm text-ink-gray-6">{{ __('Assigned to') }}</span>
        <AssignControl
          :space-code="spaceCode"
          :screen="screen"
          :name="record.name"
          :people="assigned"
          :disabled="!canWrite"
          @assigned="emit('assigned', $event)"
        />
      </li>

      <li class="flex min-h-9 items-center gap-2">
        <Icon name="lucide-paperclip" class="size-4 shrink-0 text-ink-gray-5" />
        <span class="flex-1 text-p-sm text-ink-gray-6">{{ __('Attachments') }}</span>
        <!-- A count that opens the tab that holds them, rather than a second
             uploader: there is one place files live. -->
        <Button
          variant="ghost"
          data-slot="attachments"
          :label="files === null ? __('Files') : String(files)"
          @click="emit('files')"
        />
      </li>

      <li class="flex min-h-9 items-center gap-2">
        <Icon name="lucide-tag" class="size-4 shrink-0 text-ink-gray-5" />
        <span class="flex-1 text-p-sm text-ink-gray-6">{{ __('Tags') }}</span>
        <TagControl
          :space-code="spaceCode"
          :screen="screen"
          :name="record.name"
          :tags="tags"
          :disabled="!canWrite"
          @tagged="emit('tagged', $event)"
        />
      </li>

      <li class="flex min-h-9 items-center gap-2">
        <Icon name="lucide-share-2" class="size-4 shrink-0 text-ink-gray-5" />
        <span class="flex-1 text-p-sm text-ink-gray-6">{{ __('Shared with') }}</span>
        <ShareControl
          :space-code="spaceCode"
          :screen="screen"
          :name="record.name"
          :people="shares.people || []"
          :everyone="shares.everyone || null"
          :can-share="!!shares.can_share"
          @shared="emit('shared', $event)"
        />
      </li>
    </ul>

    <!-- Who made it and who touched it last. A sentence apiece rather than a
         label-and-value grid: "Administrator, 2 days ago" is one fact. -->
    <dl class="flex flex-col gap-3 py-4">
      <div v-for="row in history" :key="row.label" class="flex flex-col gap-0.5">
        <dt class="flex min-w-0 items-center gap-1.5 text-p-sm text-ink-gray-6">
          {{ row.label }}
          <Avatar
            v-if="row.person"
            :image="row.person.image"
            :label="row.person.label"
            size="sm"
          />
          <span class="min-w-0 truncate font-medium text-ink-gray-8">
            {{ row.person ? row.person.label : row.who }}
          </span>
        </dt>
        <dd class="text-p-xs text-ink-gray-5">
          <Tooltip :text="row.exact"><span>{{ row.when }}</span></Tooltip>
        </dd>
      </div>
    </dl>

    <!--
      The id, and changing it where the doctype allows one to be changed.
      `allow_rename` is Frappe's own flag: a doctype that names its records by a
      series has an id the framework issued, which is not the same kind of thing
      as one somebody chose.
    -->
    <div
      v-if="canRename"
      class="flex items-center gap-2 border-t border-outline-gray-1 py-3"
    >
      <Icon name="lucide-hash" class="size-4 shrink-0 text-ink-gray-5" />
      <span
        data-slot="record-id"
        class="min-w-0 flex-1 truncate font-mono text-p-sm text-ink-gray-8"
      >{{ record.name }}</span>
      <Button
        data-slot="rename"
        variant="ghost"
        icon="lucide-pencil"
        :label="__('Rename')"
        :tooltip="__('Rename')"
        @click="open()"
      />
    </div>
    <!-- Where it cannot be renamed, the id is still worth showing — it is what
         a colleague will quote at you — it just is not a control. -->
    <div v-else class="flex items-center gap-2 border-t border-outline-gray-1 py-3">
      <Icon name="lucide-hash" class="size-4 shrink-0 text-ink-gray-5" />
      <span
        data-slot="record-id"
        class="min-w-0 flex-1 truncate font-mono text-p-sm text-ink-gray-8"
      >{{ record.name }}</span>
    </div>

    <Dialog v-model="renaming" :title="__('Rename this record')">
      <div class="flex flex-col gap-3">
        <FormControl
          v-model="wanted"
          type="text"
          :label="__('New id')"
          :disabled="saving"
          @keydown.enter="commit"
        />
        <p class="text-p-xs text-ink-gray-5">
          {{ __('Everything that points at this record keeps working. The old id stops.') }}
        </p>
        <ErrorMessage v-if="error" :message="error" />
      </div>
      <template #actions>
        <Button
          variant="solid"
          :label="__('Rename')"
          :loading="saving"
          :disabled="!wanted.trim() || wanted.trim() === record.name"
          @click="commit"
        />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Avatar,
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  Icon,
  Tooltip,
  dayjsLocal,
} from '@/ui'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import AssignControl from '@/modules/onespace/components/screen/fields/AssignControl.vue'
import ShareControl from '@/modules/onespace/components/screen/fields/ShareControl.vue'
import TagControl from '@/modules/onespace/components/screen/fields/TagControl.vue'
import { workspace } from '@/shared/lib/workspace'
import { useSaving } from '@/shared/composables/useSaving'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  record: { type: Object, required: true },
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
  doctype: { type: String, default: '' },
  /** The record's own name, as the identity draws it. */
  label: { type: String, default: '' },
  imageField: { type: String, default: '' },
  image: { type: String, default: '' },
  assigned: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  shares: { type: Object, default: () => ({}) },
  /** How many files are on it, or null while that is still being read. */
  files: { type: Number, default: null },
  canWrite: { type: Boolean, default: false },
  canRename: { type: Boolean, default: false },
})

const emit = defineEmits([
  'update:image', 'renamed', 'assigned', 'tagged', 'shared', 'files',
])

// "3 days ago", with the timestamp on hover — the same call the list's activity
// column makes: nobody opens a record to find out that it is 14:32.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')
const exact = (value) => (value ? dayjsLocal(value).format('D MMMM YYYY, HH:mm') : '')

const history = computed(() => {
  const record = props.record || {}
  const found = []
  // Last edited first. It is the one that changed since you last looked.
  if (record.modified && record.modified !== record.creation) {
    found.push({
      label: __('Last edited by'),
      who: record.modified_by,
      person: record._editor,
      when: when(record.modified),
      exact: exact(record.modified),
    })
  }
  if (record.owner) {
    found.push({
      label: __('Created by'),
      who: record.owner,
      person: record._owner,
      when: when(record.creation),
      exact: exact(record.creation),
    })
  }
  return found
})

// Whether the picture picker is open.
const picking = ref(false)
const renaming = ref(false)
const { saving, error, attempt } = useSaving()
const wanted = ref('')

const open = () => {
  wanted.value = props.record.name || ''
  error.value = ''
  renaming.value = true
}

// The name the *server* ended with, not the one that was typed: a doctype may
// transform what it was handed, and reporting the argument would leave the URL
// pointing at an id that was never created.
const commit = async () => {
  if (saving.value) return
  await attempt(async () => {
    const result = await workspace.rename(
      props.spaceCode,
      props.screen,
      props.record.name,
      wanted.value.trim(),
    )
    renaming.value = false
    emit('renamed', result?.name || wanted.value.trim())
  })
}
</script>

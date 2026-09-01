<template>
  <!--
    What the record is, as opposed to what it says.

    Its own tab rather than a footnote under the form. Three things live here
    and every one of them is an answer to "which record is this": the picture,
    the id, and who made it when. None is a field on the doctype, none belongs
    among the fields, and a form that ends in its own provenance puts the least
    interesting thing where the eye stops.

    One shape for all three: a properties list, label left and value right, the
    same reading a settings panel gives. What varies is the value — a picture,
    a piece of monospace, a person — and each of those is drawn the way this
    product already draws it, so nothing here is a fourth style.
  -->
  <div class="flex flex-col gap-5 pt-4">
    <!--
      The record, once, at the top: its face and its name. Not a "Picture"
      heading over a lone avatar — the picture *is* the record here, and
      changing it is something you do to what you are looking at rather than to
      a field called Image.
    -->
    <div class="flex items-center gap-3">
      <Avatar :image="image" :label="label" shape="square" size="3xl" />
      <div class="flex min-w-0 flex-col gap-1">
        <p class="truncate text-base font-medium text-ink-gray-8">{{ label }}</p>
        <FileUploader
          v-if="imageField && canWrite"
          file-types="image/*"
          :doctype="doctype"
          :docname="record.name"
          :fieldname="imageField"
          @success="(file) => emit('update:image', file.file_url)"
        >
          <template #default="{ openFileSelector, uploading }">
            <div class="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                :label="image ? 'Change picture' : 'Add a picture'"
                :loading="uploading"
                @click="openFileSelector"
              />
              <Button
                v-if="image"
                variant="ghost"
                size="sm"
                icon="lucide-trash-2"
                label="Remove the picture"
                tooltip="Remove the picture"
                @click="emit('update:image', '')"
              />
            </div>
          </template>
        </FileUploader>
      </div>
    </div>

    <!--
      The properties. A grid rather than a flex row per line, so every value
      starts on the same x however long its label is — a column of values that
      steps in and out is the thing that makes a panel look thrown together.
    -->
    <dl class="grid grid-cols-[6.5rem_minmax(0,1fr)] items-center gap-x-4 gap-y-0">
      <template v-for="row in rows" :key="row.label">
        <dt class="border-t border-outline-gray-1 py-2.5 text-p-sm text-ink-gray-5">
          {{ row.label }}
        </dt>
        <dd class="flex min-w-0 items-center gap-2 border-t border-outline-gray-1 py-2.5">
          <!-- A person is a face and a name, the same rendering a link cell
               and a stack of assignees use. An id that no longer resolves to
               anybody is still printed: "created by somebody who has left" has
               to say who. -->
          <template v-if="row.person">
            <Avatar :image="row.person.image" :label="row.person.label" size="sm" />
            <span class="truncate text-p-sm text-ink-gray-8">{{ row.person.label }}</span>
          </template>
          <span
            v-else-if="row.id"
            data-slot="record-id"
            class="min-w-0 truncate font-mono text-p-sm text-ink-gray-8"
          >{{ row.value }}</span>
          <Tooltip v-else :text="row.exact || ''">
            <span class="truncate text-p-sm text-ink-gray-8">{{ row.value }}</span>
          </Tooltip>

          <template v-if="row.id && canRename">
            <span class="flex-1" />
            <Button
              data-slot="rename"
              variant="ghost"
              size="sm"
              icon="lucide-pencil"
              label="Rename"
              tooltip="Rename"
              @click="open()"
            />
          </template>
        </dd>
      </template>
    </dl>

    <Dialog v-model="renaming" title="Rename this record">
      <div class="flex flex-col gap-3">
        <FormControl
          v-model="wanted"
          type="text"
          label="New id"
          :disabled="saving"
          @keydown.enter="commit"
        />
        <!--
          What it costs the reader, not what it costs us. "Carried over in one
          transaction" is a promise about our plumbing; "everything that points
          at it keeps working" is the thing they were worried about.
        -->
        <p class="text-p-xs text-ink-gray-5">
          Everything that points at this record keeps working. The old id stops.
        </p>
        <ErrorMessage v-if="error" :message="error" />
      </div>
      <template #actions>
        <Button
          variant="solid"
          label="Rename"
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
  FileUploader,
  FormControl,
  Tooltip,
  dayjsLocal,
} from '@/ui'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const props = defineProps({
  record: { type: Object, required: true },
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
  doctype: { type: String, default: '' },
  /** The record's own name, as the identity draws it. */
  label: { type: String, default: '' },
  imageField: { type: String, default: '' },
  image: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
  canRename: { type: Boolean, default: false },
})

const emit = defineEmits(['update:image', 'renamed'])

// "3 days ago", with the timestamp on hover — the same call the list's activity
// column makes, and for the same reason: nobody opens a record to find out that
// it is 14:32. The exact time is one hover away for the times it matters.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')
const exact = (value) => (value ? dayjsLocal(value).format('D MMMM YYYY, HH:mm') : '')

const rows = computed(() => {
  const record = props.record || {}
  const found = [{ label: 'Id', value: record.name, id: true }]

  if (record.owner) {
    found.push({
      label: 'Created by',
      value: record.owner,
      person: record._owner || { label: record.owner, image: '' },
    })
  }
  if (record.creation) {
    found.push({ label: 'Created', value: when(record.creation), exact: exact(record.creation) })
  }
  // Only where it is not the same event. A record made and never touched since
  // says "created" twice otherwise, which reads as a bug rather than as calm.
  if (record.modified && record.modified !== record.creation) {
    found.push({
      label: 'Changed',
      value: when(record.modified),
      exact: exact(record.modified),
    })
    if (record.modified_by) {
      found.push({
        label: 'Changed by',
        value: record.modified_by,
        person: record._editor || { label: record.modified_by, image: '' },
      })
    }
  }
  return found
})

const renaming = ref(false)
const saving = ref(false)
const wanted = ref('')
const error = ref('')

const open = () => {
  wanted.value = props.record.name || ''
  error.value = ''
  renaming.value = true
}

// The name the *server* ended with, not the one that was typed: a doctype may
// transform what it was handed on the way through, and reporting the argument
// would leave the URL pointing at an id that was never created.
const commit = async () => {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await workspace.rename(
      props.spaceCode,
      props.screen,
      props.record.name,
      wanted.value.trim(),
    )
    renaming.value = false
    emit('renamed', result?.name || wanted.value.trim())
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}
</script>

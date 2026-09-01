<template>
  <!--
    What the record is, as opposed to what it says.

    Its own tab rather than a footnote at the bottom of the form. Three
    unrelated things live here and they are all answers to "which record is
    this": the id, the picture, and the bookkeeping — who made it, when, and
    who touched it last. None of them is a field on the doctype, none of them
    belongs among the fields, and a form that ends in its own provenance puts
    the least interesting thing where the eye stops.
  -->
  <div class="flex flex-col gap-6 pt-4">
    <!--
      The picture. `image_field` is Frappe's own answer to "which field is the
      face of this thing" and the desk reads the same one — so a doctype that
      declares none has nothing here rather than an empty frame.
    -->
    <section v-if="imageField" class="flex flex-col gap-2">
      <h3 class="text-p-sm font-medium text-ink-gray-7">Picture</h3>
      <RecordImage
        :value="image"
        :label="label"
        :field="imageField"
        :doctype="doctype"
        :name="record.name"
        :can-write="canWrite"
        @update:value="emit('update:image', $event)"
      />
    </section>

    <!--
      The id, and changing it where the doctype allows one to be changed.
      `allow_rename` is Frappe's own flag and the desk hides its rename on the
      same one: a doctype that names its records by hash or by a series has an
      id the framework issued, and that is a different kind of thing from an id
      somebody chose.
    -->
    <section class="flex flex-col gap-2">
      <h3 class="text-p-sm font-medium text-ink-gray-7">Id</h3>
      <div class="flex items-center gap-2">
        <code
          data-slot="record-id"
          class="min-w-0 truncate rounded-6 bg-surface-gray-2 px-2 py-1 font-mono text-p-sm text-ink-gray-8"
        >{{ record.name }}</code>
        <Button
          v-if="canRename"
          data-slot="rename"
          icon-left="lucide-pencil"
          label="Rename"
          @click="open()"
        />
      </div>
      <p v-if="canRename" class="text-p-xs text-ink-gray-5">
        Everything that points at this record follows the new id. On a record
        with a great many links that can take a moment.
      </p>
    </section>

    <!--
      Who made this and when it last changed — the question every desk sidebar
      answers, and the one thing on a record that no field carries.
    -->
    <section class="flex flex-col gap-2">
      <h3 class="text-p-sm font-medium text-ink-gray-7">History</h3>
      <dl class="flex flex-col gap-1.5 text-p-xs text-ink-gray-5">
        <div v-for="row in rows" :key="row.label" class="flex items-baseline gap-2">
          <dt class="w-28 shrink-0">{{ row.label }}</dt>
          <dd class="min-w-0 truncate text-ink-gray-7">{{ row.value }}</dd>
        </div>
      </dl>
    </section>

    <Dialog v-model="renaming" title="Rename this record">
      <div class="flex flex-col gap-3">
        <FormControl
          v-model="wanted"
          type="text"
          label="New id"
          :disabled="saving"
          @keydown.enter="commit"
        />
        <p class="text-p-xs text-ink-gray-5">
          The old id stops working. Links, comments, files and assignments are
          carried over by Frappe in one transaction.
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
import { Button, Dialog, ErrorMessage, FormControl, dayjsLocal } from '@/ui'
import RecordImage from './RecordImage.vue'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const props = defineProps({
  record: { type: Object, required: true },
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
  doctype: { type: String, default: '' },
  /** The record's own name, as the identity draws it — for the image fallback. */
  label: { type: String, default: '' },
  imageField: { type: String, default: '' },
  image: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
  canRename: { type: Boolean, default: false },
})

const emit = defineEmits(['update:image', 'renamed'])

// "3 days ago" rather than a timestamp, with the timestamp on hover — the same
// call the list's activity column makes, for the same reason: nobody reads a
// record to find out that it is 14:32.
const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

const rows = computed(() => {
  const found = []
  if (props.record?.owner) {
    found.push({ label: 'Created by', value: props.record.owner })
  }
  if (props.record?.creation) {
    found.push({ label: 'Created', value: when(props.record.creation) })
  }
  // Only when it is not the same event. A record made and never touched says
  // "created" twice otherwise.
  if (props.record?.modified && props.record.modified !== props.record.creation) {
    found.push({ label: 'Last changed', value: when(props.record.modified) })
    if (props.record.modified_by) {
      found.push({ label: 'Changed by', value: props.record.modified_by })
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

// The name the *server* ended with, not the one that was typed. `before_rename`
// is a hook, and a doctype is free to transform what it was handed — reporting
// the argument would leave the URL pointing at an id that was never created.
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

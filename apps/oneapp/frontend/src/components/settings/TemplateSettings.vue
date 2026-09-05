<template>
  <!--
    A message written once and sent often.

    The last row open in `docs/EMAIL.md` §6, and the smallest: a shared address
    answers the same five questions all week — where the order is, what the lead
    time is, which documents we need — and typing the answer again each time is
    slow and inconsistent, which is the half a customer notices.

    Written here, used in the composer: the same list, not an admin's copy of
    one. Writing one is deciding what the workspace says to a customer, so it is
    an admin's; using one is answering an email, so it is anybody's.
  -->
  <SettingsHeader
    title="Message templates"
    description="A reply written once, ready to send again."
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button icon-left="lucide-plus" label="New template" @click="start()" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <Alert v-else-if="error" theme="red" title="Templates could not be loaded">
      <template #description>{{ error }}</template>
    </Alert>

    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-file-text"
      title="No templates yet"
      description="A template is a subject and a message somebody can send without writing it again."
    >
      <template #action>
        <Button icon-left="lucide-plus" label="New template" @click="start()" />
      </template>
    </EmptyState>

    <div v-else class="flex flex-col gap-3 py-4">
      <article
        v-for="row in rows"
        :key="row.name"
        class="flex items-start justify-between gap-3 rounded-6 border border-outline-gray-2 p-4"
        data-slot="mail-template"
      >
        <div class="flex min-w-0 flex-col gap-1">
          <span class="truncate text-p-sm font-medium text-ink-gray-8">{{ row.name }}</span>
          <span class="truncate text-p-xs text-ink-gray-6">{{ row.subject }}</span>
          <span v-if="row.doctype" class="text-p-xs text-ink-gray-5">
            For {{ row.doctype }}
            <!-- A template written for a record the workspace no longer has is
                 one it cannot use. Shown and said, because hiding it would
                 leave something nobody can find to delete. -->
            <span v-if="row.orphaned">— which this workspace no longer has</span>
          </span>
        </div>

        <div class="flex shrink-0 items-center gap-1">
          <Button
            variant="ghost"
            icon="lucide-pencil"
            label="Edit"
            tooltip="Edit"
            @click="start(row)"
          />
          <Button
            variant="ghost"
            icon="lucide-trash-2"
            label="Remove"
            tooltip="Remove"
            @click="remove(row)"
          />
        </div>
      </article>
    </div>
  </SettingsBody>

  <!--
    Outside `SettingsBody`, the same way the alert editor is: a Dialog is not
    part of the panel that opened it, and its Save is its own rather than the
    panel's pinned action.
  -->
  <Dialog v-model="writing" :title="draft.name ? 'Edit template' : 'New template'" size="xl">
    <div class="flex flex-col gap-3">
      <FormControl
        v-model="draft.title"
        label="Name"
        placeholder="Delivery update"
        description="What it is called in the picker."
      />
      <FormControl
        v-model="draft.subject"
        label="Subject"
        placeholder="Your order is on its way"
      />
      <Select
        v-model="draft.doctype"
        label="For a record"
        :options="doctypeOptions"
        :description="FIELDS_HINT"
      />

      <!--
        The same editor the composer writes in, because this is what it will
        be. `{{ doc.customer }}` fills in from the record it is sent from —
        which is the whole reason a template may name one.
      -->
      <div class="rounded-6 border border-outline-gray-2 bg-surface-base px-3 py-2">
        <Editor
          v-model="draft.body"
          :extensions="EXTENSIONS"
          format="html"
          placeholder="Write the message"
        >
          <template #default="{ editor }">
            <EditorFixedMenu :editor="editor" :items="articleToolbar" class="mb-2" />
            <EditorContent :editor="editor" aria-label="Template" dir="auto" />
          </template>
        </Editor>
      </div>

      <ErrorMessage v-if="saveError" :message="saveError" />
    </div>
    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save()" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  Alert,
  Button,
  Dialog,
  Editor,
  EditorContent,
  EditorFixedMenu,
  ErrorMessage,
  FormControl,
  LoadingText,
  RichTextKit,
  Select,
  SettingsBody,
  SettingsHeader,
  articleToolbar,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const EXTENSIONS = [RichTextKit]

// In the script rather than in the attribute: the braces are the point, and a
// mustache inside a Vue template attribute is a fight nobody needs to have.
const FIELDS_HINT = "A template written for a record can say {{ doc.customer }} and mean it."

const rows = ref([])
const doctypes = ref([])
const loading = ref(true)
const error = ref('')

const writing = ref(false)
const saving = ref(false)
const saveError = ref('')
const draft = reactive({ name: '', title: '', subject: '', doctype: '', body: '' })

// The records this workspace has, from the same list the alert form offers —
// one answer to "what can a rule be about", not two.
const doctypeOptions = computed(() => [
  { label: 'Any record', value: '' },
  ...doctypes.value.map((one) => ({ label: one.label || one.value, value: one.value })),
])

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = (await workspace.mailTemplates()) || []
    // Best effort: a workspace with no alertable doctypes still has templates,
    // and a failure here should cost the picker rather than the panel.
    doctypes.value = (await workspace.alerts().catch(() => null))?.doctypes || []
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    loading.value = false
  }
}

function start(row = null) {
  saveError.value = ''
  Object.assign(draft, {
    name: row?.name || '',
    title: row?.name || '',
    subject: row?.subject || '',
    doctype: row?.doctype || '',
    body: row?.body || '',
  })
  writing.value = true
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    await workspace.saveMailTemplate({ ...draft })
    writing.value = false
    await load()
  } catch (raised) {
    saveError.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await workspace.removeMailTemplate(row.name)
  await load()
}

load()
</script>

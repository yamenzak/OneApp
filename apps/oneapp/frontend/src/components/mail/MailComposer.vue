<template>
  <Dialog v-model="open" :title="title" size="xl">
    <div class="flex flex-col gap-3">
      <Select
        v-if="addresses.length > 1"
        v-model="draft.sender"
        label="From"
        :options="addresses.map((one) => ({ label: one, value: one }))"
      />
      <!-- Stacked on a phone. Side by side, the toggle takes a third of the
           line and leaves the recipients a box too narrow to read one
           address in, which is the field that matters most on the screen
           with the least room. -->
      <div class="flex flex-col items-stretch gap-2 sm:flex-row sm:items-end">
        <RecipientField v-model="draft.to" class="flex-1" label="To" />
        <!-- Behind a toggle, because most messages have neither and two
             empty boxes above every one of them is two boxes to skip. -->
        <Button
          variant="ghost"
          class="self-start sm:self-auto"
          :label="copies ? 'Hide Cc and Bcc' : 'Cc and Bcc'"
          data-slot="mail-copies"
          @click="copies = !copies"
        />
      </div>
      <RecipientField v-if="copies" v-model="draft.cc" label="Cc" placeholder="Also to" />
      <RecipientField v-if="copies" v-model="draft.bcc" label="Bcc" placeholder="Privately to" />
      <FormControl v-model="draft.subject" label="Subject" />

      <!--
        The same editor a Text Editor field gets, with the same extensions:
        mail is prose, and a textarea sends a paragraph of plain text to
        somebody whose client will render it as one long line. `Editor` is
        renderless — it owns the model, the upload and the placeholder and
        draws nothing — so the toolbar is a choice made here.
      -->
      <div class="rounded-6 border border-outline-gray-2 bg-surface-base px-3 py-2">
        <Editor
          v-model="draft.content"
          :extensions="EXTENSIONS"
          format="html"
          placeholder="Write your message"
          :upload-function="uploadInline"
        >
          <template #default="{ editor }">
            <EditorFixedMenu :editor="editor" :items="articleToolbar" class="mb-2" />
            <EditorContent :editor="editor" aria-label="Message" dir="auto" />
          </template>
        </Editor>
      </div>

      <!-- What is going with it. A forward arrives here already carrying the
           original's files; anything else is added below. -->
      <div v-if="draft.attachments.length" class="flex flex-wrap gap-2">
        <span
          v-for="one in draft.attachments"
          :key="one.name"
          class="flex items-center gap-1.5 rounded-6 border border-outline-gray-2 px-2 py-1 text-p-xs text-ink-gray-7"
          data-slot="mail-attachment"
        >
          <Icon name="lucide-paperclip" class="size-3" :aria-hidden="true" />
          {{ one.file_name }}
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-x"
            :label="`Remove ${one.file_name}`"
            :tooltip="`Remove ${one.file_name}`"
            @click="unattach(one)"
          />
        </span>
      </div>

      <FileUploader :private="true" @success="attach">
        <template #default="{ openFileSelector, uploading }">
          <Button
            variant="subtle"
            icon-left="lucide-paperclip"
            :label="uploading ? 'Attaching…' : 'Attach a file'"
            data-slot="mail-attach"
            @click="openFileSelector()"
          />
        </template>
      </FileUploader>

      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button variant="solid" label="Send" :loading="sending" @click="post" />
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

import {
  Button,
  Dialog,
  Editor,
  EditorContent,
  EditorFixedMenu,
  ErrorMessage,
  FileUploader,
  FormControl,
  Icon,
  RichTextKit,
  Select,
  articleToolbar,
  upload,
} from '@/ui'
import RecipientField from './RecipientField.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  /** The addresses this person may send from. The first is the default. */
  addresses: { type: Array, default: () => [] },
})
const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['sent'])

const draft = reactive({
  sender: '', to: '', cc: '', bcc: '', subject: '', content: '',
  in_reply_to: '', attachments: [],
})
// Behind a toggle, because most messages have neither Cc nor Bcc and two empty
// boxes above every one of them is two boxes to skip.
const copies = ref(false)
const sending = ref(false)
const error = ref('')
const title = ref('New message')

const EXTENSIONS = [RichTextKit]
const uploadInline = (file) => upload(file, { private: true })

/** A file finished uploading — remember it for the send. */
function attach(file) {
  draft.attachments.push({ name: file.name, file_name: file.file_name || file.name })
}

function unattach(one) {
  draft.attachments = draft.attachments.filter((row) => row.name !== one.name)
}

const TITLES = { reply: 'Reply', reply_all: 'Reply to all', forward: 'Forward' }

const blank = () => {
  Object.assign(draft, {
    to: '', cc: '', bcc: '', subject: '', content: '', in_reply_to: '', attachments: [],
  })
}

/**
 * Open the composer, blank or carrying a message.
 *
 * The carrying case is built on the server — see `mailbox.draft`. Quoting in
 * the browser would quote the copy the reader is looking at, which has had its
 * remote images held back, and send somebody a reply full of empty `<img>`.
 */
async function compose(from, kind = 'reply') {
  error.value = ''
  copies.value = false
  blank()
  title.value = 'New message'

  if (from) {
    title.value = TITLES[kind] || 'Reply'
    const opening = await workspace.mailDraft(from.name, kind)
    Object.assign(draft, opening, { bcc: '' })
    draft.attachments = opening.attachments || []
    copies.value = !!opening.cc
  } else {
    // A blank composer opens on whatever was left behind, if anything was.
    const opening = await workspace.mailKept()
    if (opening && Object.keys(opening).length) {
      Object.assign(draft, opening)
      copies.value = !!(opening.cc || opening.bcc)
    }
    if (!draft.sender) draft.sender = props.addresses[0] || ''
  }
  open.value = true
}

/** Back into the composer with what was just unsent, held server-side. */
async function reopen() {
  Object.assign(draft, await workspace.mailKept())
  open.value = true
}

async function post() {
  error.value = ''
  sending.value = true
  try {
    const done = await workspace.mailSend({
      ...draft,
      // Names, not the files. They are already on the site; sending the bytes
      // back through this call would be a second upload of what we hold.
      attachments: JSON.stringify(draft.attachments.map((one) => one.name)),
    })
    open.value = false
    await workspace.mailForget()
    emit('sent', done)
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    sending.value = false
  }
}

// Closing the composer by accident and losing a written message is the failure
// people remember. Held server-side rather than in this browser, so it survives
// the tab as well as the dialog.
let keeping = null
watch(
  () => [draft.to, draft.cc, draft.bcc, draft.subject, draft.content].join('\u0000'),
  () => {
    if (!open.value) return
    clearTimeout(keeping)
    keeping = setTimeout(() => workspace.mailKeep({ ...draft }), 800)
  },
)

defineExpose({ compose, reopen })
</script>

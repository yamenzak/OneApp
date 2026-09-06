<template>
  <Dialog v-model="open" :title="title" size="xl">
    <div class="flex flex-col gap-3">
      <Select
        v-if="addresses.length > 1"
        v-model="draft.sender"
        :label="__('From')"
        :options="addresses.map((one) => ({ label: one, value: one }))"
      />
      <!-- Stacked on a phone: side by side, the toggle leaves the recipients
           a box too narrow to read one address in. -->
      <div class="flex flex-col items-stretch gap-2 sm:flex-row sm:items-end">
        <RecipientField v-model="draft.to" class="flex-1" :label="__('To')" />
        <!-- Behind a toggle, because most messages have neither and two empty
             boxes above every one of them is two boxes to skip. -->
        <Button
          variant="ghost"
          class="self-start sm:self-auto"
          :label="copies ? __('Hide Cc and Bcc') : __('Cc and Bcc')"
          data-slot="mail-copies"
          @click="copies = !copies"
        />
      </div>
      <RecipientField
        v-if="copies"
        v-model="draft.cc"
        :label="__('Cc')"
        :placeholder="__('Also to')"
      />
      <RecipientField
        v-if="copies"
        v-model="draft.bcc"
        :label="__('Bcc')"
        :placeholder="__('Privately to')"
      />
      <FormControl v-model="draft.subject" :label="__('Subject')" />

      <!--
        The same editor a Text Editor field gets: mail is prose, and a textarea
        sends a paragraph of plain text to somebody whose client renders it as
        one long line. `Editor` is renderless, so the toolbar is a choice made
        here.
      -->
      <div class="rounded-6 border border-outline-gray-2 bg-surface-base px-3 py-2">
        <Editor
          v-model="draft.content"
          :extensions="EXTENSIONS"
          format="html"
          :placeholder="__('Write your message')"
          :upload-function="uploadInline"
        >
          <template #default="{ editor }">
            <EditorFixedMenu :editor="editor" :items="articleToolbar" class="mb-2" />
            <EditorContent :editor="editor" :aria-label="__('Message')" dir="auto" />
          </template>
        </Editor>
      </div>

      <!-- What is going with it. A forward arrives carrying the original's
           files; anything else is added below. -->
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
            :label="__('Remove {0}', [one.file_name])"
            :tooltip="__('Remove {0}', [one.file_name])"
            @click="unattach(one)"
          />
        </span>
      </div>

      <!-- Upload one, or send one the workspace already has. Upload-only meant
           attaching last week's drawing twice and paying for it twice. -->
      <div class="flex flex-wrap gap-2">
        <Button
          variant="subtle"
          icon-left="lucide-paperclip"
          :label="__('Attach a file')"
          data-slot="mail-attach"
          @click="picking = true"
        />
        <!--
          A message written once and sent often. Only where there is one to use:
          a button that opens an empty menu teaches people not to press it.
        -->
        <Dropdown v-if="templates.length || session.isAdmin" :options="templateOptions">
          <Button
            variant="subtle"
            icon-left="lucide-file-text"
            :label="__('Use a template')"
            data-slot="mail-templates"
          />
        </Dropdown>
      </div>
      <FilePicker v-model="picking" multiple @picked="attach" />

      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button variant="solid" :label="__('Send')" :loading="sending" @click="post" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import {
  Button,
  Dialog,
  Dropdown,
  Editor,
  EditorContent,
  EditorFixedMenu,
  ErrorMessage,
  FormControl,
  Icon,
  RichTextKit,
  Select,
  articleToolbar,
  upload,
} from '@/ui'
import RecipientField from './RecipientField.vue'
import { withSignature } from './signature'
import { mail } from '@/lib/shell/mail'
import FilePicker from '../drive/FilePicker.vue'
import { workspace } from '../../lib/workspace'
import { session } from '@/lib/shell/session'
import { openSettings } from '@/lib/shell/settings'
import { __ } from '@/lib/runtime/translate'

const props = defineProps({
  /** The addresses this person may send from. The first is the default. */
  addresses: { type: Array, default: () => [] },
  /**
   * What this message is about, when it is written from a record:
   * `{ spaceCode, screen, name }`. Sending through the record's own endpoint is
   * what files the message against it — the one filing here that needs no
   * working out, because the person was looking at the record.
   */
  about: { type: Object, default: null },
})
const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['sent'])

const draft = reactive({
  sender: '', to: '', cc: '', bcc: '', subject: '', content: '',
  in_reply_to: '', attachments: [],
})
// Behind a toggle, because most messages have neither Cc nor Bcc.
const copies = ref(false)
// Whether the attach picker is open.
const picking = ref(false)
const sending = ref(false)
const error = ref('')
const title = ref(__('New message'))

/** The workspace's templates, read once per composer opening. */
const templates = ref([])

const templateOptions = computed(() => [
  ...templates.value.map((one) => ({
    // The name *is* the title: `Email Template` is named by prompt, so two
    // called "Delivery update" would be two rows nobody could tell apart.
    label: one.name,
    // The record a template is for, where it names one.
    description: one.doctype || '',
    onClick: () => use(one),
  })),
  // Where they are written, one dialog away — rather than a second editor in
  // here. Only for somebody who may: the tab is an admin's.
  ...(session.isAdmin
    ? [{
        label: __('Manage templates…'),
        icon: 'lucide-settings',
        onClick: () => openSettings('templates'),
      }]
    : []),
])

/**
 * Put a template into the message. The subject is replaced; the body is written
 * *above* whatever is there, because what is there is a quote, a signature, or
 * both.
 */
async function use(one) {
  const filled = props.about
    ? await workspace.recordMailTemplate(
        props.about.spaceCode, props.about.screen, props.about.name, one.name,
      )
    : await workspace.mailTemplate(one.name)

  if (filled?.subject) draft.subject = filled.subject
  draft.content = `${filled?.message || ''}${draft.content || ''}`
}

const EXTENSIONS = [RichTextKit]
const uploadInline = (file) => upload(file, { private: true })

/** A file finished uploading — remember it for the send. */
function attach(file) {
  draft.attachments.push({ name: file.name, file_name: file.file_name || file.name })
}

function unattach(one) {
  draft.attachments = draft.attachments.filter((row) => row.name !== one.name)
}

const titleFor = (kind) =>
  ({
    reply: __('Reply'),
    reply_all: __('Reply to all'),
    forward: __('Forward'),
  })[kind] || __('Reply')

/**
 * Sign the message with whatever the From address signs with.
 *
 * The signature belongs to the address rather than to the person, because an
 * address here is a mailbox several people share — so changing From changes the
 * sign-off, in front of somebody rather than on the way out. See
 * `email/signatures.py`.
 */
const sign = (was = '') => {
  draft.content = withSignature(
    draft.content,
    mail.signatures[draft.sender] || '',
    mail.signatures[was] || '',
  )
}

const blank = () => {
  Object.assign(draft, {
    to: '', cc: '', bcc: '', subject: '', content: '', in_reply_to: '', attachments: [],
  })
}

/**
 * Which address this message goes out as, asked rather than guessed.
 *
 * `props.addresses[0]` was whatever `User Email` came back first, so somebody
 * with a company address and one on our own domain sent from whichever the
 * database happened to order — the one thing about this a customer notices and
 * does not forgive.
 */
async function sendingFrom(about = {}) {
  const answer = await workspace.mailSendingFrom({
    ...about,
    ...(props.about
      ? { doctype: props.about.doctype || '', name: props.about.name || '' }
      : {}),
  })
  return answer?.sender || props.addresses[0] || ''
}

/**
 * Open the composer, blank or carrying a message. The carrying case is built on
 * the server — see `mailbox.draft`: quoting in the browser would quote the copy
 * the reader is looking at, whose remote images have been held back.
 */
async function compose(from, kind = 'reply') {
  error.value = ''
  copies.value = false
  blank()
  title.value = __('New message')

  // Read on opening rather than held: a template written a minute ago should be
  // in the list.
  workspace.mailTemplates().then((found) => { templates.value = found || [] })

  if (from) {
    title.value = titleFor(kind)
    const opening = await workspace.mailDraft(from.name, kind)
    Object.assign(draft, opening, { bcc: '' })
    draft.attachments = opening.attachments || []
    copies.value = !!opening.cc
    // A reply goes out as the address it arrived at. The server decides, from
    // the message and the record — see `mailbox.sending.default_sender` — so
    // the browser is not holding a second copy of that rule.
    draft.sender = (await sendingFrom({ in_reply_to: from.name })) || draft.sender
    sign()
  } else {
    // A blank composer opens on whatever was left behind, if anything was.
    const opening = await workspace.mailKept()
    if (opening && Object.keys(opening).length) {
      Object.assign(draft, opening)
      copies.value = !!(opening.cc || opening.bcc)
    }
    if (!draft.sender) draft.sender = await sendingFrom()
    // Only for a message that has not been started: what was kept was kept with
    // its signature in it, and signing it again would sign what somebody may
    // have deliberately deleted.
    if (!draft.content) sign()
  }
  open.value = true
}

// Changing who it is from changes what signs it — and only that. `sign()` swaps
// the block it owns, which is what makes this safe over a half-written message.
watch(() => draft.sender, (address, was) => {
  if (open.value && was && address !== was) sign(was)
})

/** Back into the composer with what was just unsent, held server-side. */
async function reopen() {
  Object.assign(draft, await workspace.mailKept())
  open.value = true
}

async function post() {
  error.value = ''
  sending.value = true
  try {
    const values = {
      ...draft,
      // Names, not the files. They are already on the site; sending the bytes
      // back would be a second upload of what we hold.
      attachments: JSON.stringify(draft.attachments.map((one) => one.name)),
    }
    const done = props.about
      ? await workspace.recordMailSend(
          props.about.spaceCode, props.about.screen, props.about.name, values,
        )
      : await workspace.mailSend(values)
    open.value = false
    await workspace.mailForget()
    emit('sent', done)
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    sending.value = false
  }
}

/**
 * Whether there is a message here, as opposed to a composer that was opened.
 * The signature does not count — it is put in before anybody types a word, so
 * without this every opened-and-closed composer left a draft behind it.
 */
const written = () => {
  if (draft.to || draft.cc || draft.bcc || draft.subject) return true
  const bare = withSignature(draft.content, '', mail.signatures[draft.sender] || '')
  return new DOMParser().parseFromString(bare, 'text/html').body.textContent.trim() !== ''
}

// Closing the composer by accident and losing a written message is the failure
// people remember. Held server-side, so it survives the tab as well as the
// dialog.
let keeping = null
watch(
  () => [draft.to, draft.cc, draft.bcc, draft.subject, draft.content].join('\u0000'),
  () => {
    if (!open.value) return
    clearTimeout(keeping)
    keeping = setTimeout(() => {
      if (written()) workspace.mailKeep({ ...draft })
    }, 800)
  },
)

defineExpose({ compose, reopen })
</script>

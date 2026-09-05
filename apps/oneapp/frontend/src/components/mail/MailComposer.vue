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

      <!--
        Upload one, or send one the workspace already has. Before the picker
        this was upload-only, so attaching last week's drawing to a second
        email meant uploading it a second time and paying for it twice.
      -->
      <div class="flex flex-wrap gap-2">
        <Button
          variant="subtle"
          icon-left="lucide-paperclip"
          label="Attach a file"
          data-slot="mail-attach"
          @click="picking = true"
        />
        <!--
          A message written once and sent often. A shared address answers the
          same five questions all week, and typing the answer again each time is
          both slow and inconsistent — which is the half a customer notices.
          Only where there is one to use: a button that opens an empty menu is
          a button that teaches people not to press it.
        -->
        <Dropdown v-if="templates.length" :options="templateOptions">
          <Button
            variant="subtle"
            icon-left="lucide-file-text"
            label="Use a template"
            data-slot="mail-templates"
          />
        </Dropdown>
      </div>
      <FilePicker v-model="picking" multiple @picked="attach" />

      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button variant="solid" label="Send" :loading="sending" @click="post" />
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
import { mail } from '../../lib/mail'
import FilePicker from '../drive/FilePicker.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  /** The addresses this person may send from. The first is the default. */
  addresses: { type: Array, default: () => [] },
  /**
   * What this message is about, when it is written from a record rather than
   * from the Mail screen: `{ spaceCode, screen, name }`.
   *
   * Sending through the record's own endpoint is what files the message
   * against it — and that is the one filing in this product that needs no
   * working out at all, because the person was looking at the record when they
   * wrote it. Everything else about the composer is the same either way, which
   * is why this is a prop and not a second composer.
   */
  about: { type: Object, default: null },
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
// Whether the attach picker is open.
const picking = ref(false)
const sending = ref(false)
const error = ref('')
const title = ref('New message')

/** The workspace's templates, read once per composer opening. */
const templates = ref([])

const templateOptions = computed(() =>
  templates.value.map((one) => ({
    // The name *is* the title: `Email Template` is named by prompt, so two
    // called "Delivery update" would be two rows nobody could tell apart.
    label: one.name,
    // The record a template is for, where it names one: "Quotation" beside a
    // template written for quotations is the difference between picking the
    // right one and reading four.
    description: one.doctype || '',
    onClick: () => use(one),
  })),
)

/**
 * Put a template into the message.
 *
 * The subject is replaced; the body is written *above* whatever is there,
 * because what is there is a quote, a signature, or both — and a template that
 * ate somebody's signature would be a template nobody used twice.
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

const TITLES = { reply: 'Reply', reply_all: 'Reply to all', forward: 'Forward' }

/**
 * Sign the message with whatever the From address signs with.
 *
 * The signature belongs to the address rather than to the person, because an
 * address here is a mailbox several people share — so changing From changes the
 * sign-off, and it changes in front of somebody rather than on the way out.
 * That was the bug this closes: the signature people typed into settings was
 * never used at all, and the framework's own rule appended the *default
 * outgoing* account's one to everything. See `email/signatures.py`.
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

  // Read on opening rather than held: a template written a minute ago should be
  // in the list, and this is one small request against a dialog somebody is
  // about to spend a minute in.
  workspace.mailTemplates().then((found) => { templates.value = found || [] })

  if (from) {
    title.value = TITLES[kind] || 'Reply'
    const opening = await workspace.mailDraft(from.name, kind)
    Object.assign(draft, opening, { bcc: '' })
    draft.attachments = opening.attachments || []
    copies.value = !!opening.cc
    sign()
  } else {
    // A blank composer opens on whatever was left behind, if anything was.
    const opening = await workspace.mailKept()
    if (opening && Object.keys(opening).length) {
      Object.assign(draft, opening)
      copies.value = !!(opening.cc || opening.bcc)
    }
    if (!draft.sender) draft.sender = props.addresses[0] || ''
    // Only for a message that has not been started. What was kept was kept with
    // its signature in it, and signing it again would be signing what somebody
    // may have deliberately deleted.
    if (!draft.content) sign()
  }
  open.value = true
}

// Changing who it is from changes what signs it — and only that. `sign()`
// swaps the block it owns and leaves everything else where it is, which is
// what makes this safe to run over a half-written message.
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
      // back through this call would be a second upload of what we hold.
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
 *
 * The signature does not count. It is put in before anybody types a word, so
 * without this every opened-and-closed composer left a draft behind it — and
 * the next blank message opened carrying a sign-off, a subject and a recipient
 * from a message somebody had decided not to write.
 */
const written = () => {
  if (draft.to || draft.cc || draft.bcc || draft.subject) return true
  const bare = withSignature(draft.content, '', mail.signatures[draft.sender] || '')
  return new DOMParser().parseFromString(bare, 'text/html').body.textContent.trim() !== ''
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
    keeping = setTimeout(() => {
      if (written()) workspace.mailKeep({ ...draft })
    }, 800)
  },
)

defineExpose({ compose, reopen })
</script>

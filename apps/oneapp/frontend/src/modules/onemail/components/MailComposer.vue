<template>
  <!-- Wider with the rail out, rather than the message getting narrower to
       make room for it: the composer is already as narrow as prose wants to
       be, and a rail that took a third of it would be a rail people close. -->
  <Dialog v-model="open" :title="title" :size="rail ? '4xl' : 'xl'">
    <div class="flex gap-4">
      <div class="flex min-w-0 flex-1 flex-col gap-3">
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
            ref="body"
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
          <!-- What the message is about, and its numbers a click away rather
               than read off another tab and typed. -->
          <Button
            variant="subtle"
            icon-left="lucide-link"
            :label="rail ? __('Hide records') : __('Records')"
            data-slot="mail-records"
            @click="rail = !rail"
          />
        </div>
        <FilePicker v-model="picking" multiple @picked="attach" />

        <ErrorMessage v-if="error" :message="error" />
      </div>

      <!--
        The same rail a document and a workbook have, and it does a different
        thing here: a field goes in as the *text* it says, not as a token.
        There is nothing to keep live — a sent message cannot be read again —
        so `live` is false and the panel drops Refresh and its "Read at".

        The sources are held in this component rather than as `Bound Record`
        rows, because a draft is not a `File` and there is nothing to hang one
        off. Adding, choosing and dropping come back as events; see the note
        at the top of `RecordPanel.vue`.
      -->
      <RecordPanel
        v-if="rail"
        class="max-h-[32rem]"
        :sources="sources"
        :values="values"
        :busy="reading"
        :live="false"
        can-write
        :said="__('The message will carry what this record says now. What you put in is text, so it does not change afterwards.')"
        @insert-field="insertField"
        @insert-table="insertTable"
        @add-source="addSource"
        @set-source="setSource"
        @drop-source="dropSource"
        @close="rail = false"
      />
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
import RecipientField from '@/modules/onemail/components/RecipientField.vue'
import RecordPanel from '@/shared/components/RecordPanel.vue'
import { withSignature } from '@/modules/onemail/components/signature'
import { mail } from '@/modules/onespace/lib/shell/mail'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import { workspace } from '@/shared/lib/workspace'
import { session } from '@/modules/onespace/lib/shell/session'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const props = defineProps({
  /** The addresses this person may send from. The first is the default. */
  addresses: { type: Array, default: () => [] },
  /**
   * What this message is about, when it is written from a record:
   * `{ spaceCode, screen, name }`. Sending through the record's own endpoint is
   * what files the message against it — the one filing here that needs no
   * working out, because the person was looking at the record.
   *
   * `doctype` is optional and only the rail reads it: with one, the record
   * this was written from is the first thing the rail offers, which is the
   * whole of "reply to the customer with the quotation's total in it".
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

/*
 * The records this message is about, and what they say.
 *
 * Held here rather than as `Bound Record` rows: a draft is a thing in a
 * browser until it is sent, and there is nothing for a row to point at. The
 * key is only the rail's own handle — a document's token names one forever,
 * which is why the server keeps them stable, and nothing in a sent message
 * names one at all.
 *
 * `values` fills in as fields are picked rather than up front. A doctype
 * offers ninety of them and a message uses three, so reading all ninety on
 * every opening would buy a preview nobody asked for; picking one reads it,
 * and the preview is there from then on.
 */
const rail = ref(false)
const sources = ref([])
const values = ref({})
const reading = ref(false)

//: The rich-text editor, for putting something in where the cursor is. It
//: exposes `{ editor, isEmpty }`; nothing here owns its lifecycle.
const body = ref(null)

//: How many records one message may be about — `binding.MAX_SOURCES`, and the
//: same reason: past this it is a report rather than a letter.
const MAX_SOURCES = 12

//: `frappe.scrub`, which is what the server derives a key with.
const scrub = (text) => (text || '').trim().toLowerCase().replace(/[\s-]+/g, '_')

function keyFor(doctype) {
  const taken = new Set(sources.value.map((one) => one.key))
  // The first source is what a bare key means, whatever it is of — kept the
  // same as the server's so the two rails read alike.
  if (!taken.size) return 'record'
  const stem = scrub(doctype) || 'record'
  if (!taken.has(stem)) return stem
  let at = 2
  while (taken.has(`${stem}_${at}`)) at += 1
  return `${stem}_${at}`
}

/** One row in the shape `binding.file_sources` answers in. */
const sourceRow = (doctype, name, title) => ({
  key: keyFor(doctype),
  label: doctype,
  reference_doctype: doctype,
  reference_name: name || '',
  title: title || '',
})

function addSource({ doctype, name, title }) {
  if (!doctype || sources.value.length >= MAX_SOURCES) return
  sources.value = [...sources.value, sourceRow(doctype, name, title)]
}

function setSource({ key, doctype, name, title }) {
  sources.value = sources.value.map((one) => (
    one.key === key
      ? { ...one, reference_doctype: doctype || one.reference_doctype,
          reference_name: name || '', title: title || '' }
      : one
  ))
  forget(key)
}

function dropSource({ key }) {
  sources.value = sources.value.filter((one) => one.key !== key)
  forget(key)
}

/** Drop what a source said. Its previews are about a record it no longer is. */
function forget(key) {
  const next = {}
  for (const [at, text] of Object.entries(values.value)) {
    if (!at.startsWith(`${key}.`)) next[at] = text
  }
  values.value = next
}

/** Ask what these fields say, and remember it for the previews. */
async function read(row, wanted) {
  const answer = await workspace.bindableValues(
    row.reference_doctype, row.reference_name, wanted,
  )
  const said = answer?.fields || {}
  const next = { ...values.value }
  for (const [field, one] of Object.entries(said)) {
    next[`${row.key}.${field}`] = one?.text ?? ''
  }
  values.value = next
  return said
}

/**
 * Put something where the cursor is.
 *
 * A text node rather than a string, because `insertContent` parses a string
 * as HTML and a customer called `Smith & Sons <UK>` would arrive as a broken
 * tag. A table is HTML and is inserted as HTML — see `insertTable`.
 */
function put(content) {
  const editor = body.value?.editor
  if (!editor || !content) return
  editor.chain().focus().insertContent(content).run()
}

async function insertField(one) {
  const row = sources.value.find((each) => each.key === one.source)
  if (!row?.reference_name) return

  let text = values.value[`${one.source}.${one.field}`]
  if (text === undefined) {
    reading.value = true
    try {
      text = (await read(row, [one.field]))[one.field]?.text ?? ''
    } catch {
      // A field this person cannot read, or a record that moved. Nothing goes
      // in, which is the honest answer — a blank in a message somebody is
      // about to send would be worse.
      return
    } finally {
      reading.value = false
    }
  }
  if (text) put({ type: 'text', text })
}

/**
 * A child table, as a real table in the message.
 *
 * The rows are frozen the moment they go in, height and all — which is what
 * a mail is. The document's block keeps its cells live and the workbook's
 * grid recomputes them; here there is nothing left to recompute.
 */
async function insertTable(one) {
  const row = sources.value.find((each) => each.key === one.source)
  if (!row?.reference_name) return

  reading.value = true
  let found
  try {
    found = await workspace.bindableRows(
      row.reference_doctype, row.reference_name, one.table, one.columns || [],
    )
  } catch {
    return
  } finally {
    reading.value = false
  }

  const columns = found?.columns || []
  if (!columns.length) return
  put(tableHtml(columns, found?.rows || []))
}

const escape = (text) => String(text ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')

/** A schedule as the HTML a mail client will render. */
function tableHtml(columns, lines) {
  const head = columns.map((one) => `<th>${escape(one.label)}</th>`).join('')
  const rows = lines
    .map((line) => `<tr>${line.map((cell) => `<td>${escape(cell)}</td>`).join('')}</tr>`)
    .join('')
  return `<table><tbody><tr>${head}</tr>${rows}</tbody></table>`
}

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

  // What the rail starts on. A message written from a record is about that
  // record, which is the one binding nobody has to work out — and the rail
  // stays shut until somebody asks for it, because most messages are prose.
  rail.value = false
  values.value = {}
  sources.value = props.about?.doctype && props.about?.name
    ? [sourceRow(props.about.doctype, props.about.name, props.about.title || '')]
    : []

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
    error.value = errorText(e)
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

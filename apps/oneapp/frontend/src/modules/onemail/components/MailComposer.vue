<template>
  <!-- Wider with the rail out, rather than the message getting narrower to
       make room for it: the composer is already as narrow as prose wants to
       be, and a rail that took a third of it would be a rail people close. -->
  <ComposerFrame v-model="open" :pane="pane" :title="title" :size="rail ? '4xl' : 'xl'">
    <!-- The rail goes under the message rather than beside it in a pane: the
         reading column is one column wide, and a rail taking a third of it
         leaves the prose narrower than the message it is answering. -->
    <div class="flex gap-4" :class="pane ? 'flex-col' : ''">
      <div class="flex min-w-0 flex-1 flex-col gap-3">
        <Select
          v-if="addresses.length > 1"
          v-model="draft.sender"
          :label="__('From')"
          :options="addresses.map((one) => ({ label: one, value: one }))"
        />
        <!-- Stacked on a phone: side by side, the toggle leaves the recipients
             a box too narrow to read one address in. -->
        <div class="flex flex-col items-stretch gap-2 md:flex-row md:items-end">
          <RecipientField v-model="draft.to" class="flex-1" :label="__('To')" />
          <!--
            Behind a toggle, because most messages have neither and two empty
            boxes above every one of them is two boxes to skip.

            `subtle` and not `ghost`: a borderless control on its own line
            under a labelled field is read as another label, which is what it
            looked like on a phone. The chevron says the same thing a second
            way — there is something under this — and turns over when there
            is, so the state is legible without reading the word.
          -->
          <Button
            variant="subtle"
            class="self-start md:self-auto"
            :icon-left="copies ? 'lucide-chevron-up' : 'lucide-chevron-down'"
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
        <!--
          The glow is over the whole body rather than beside it, because what
          is arriving *is* the body: a sheen on the pane says these words are
          being written, and a spinner in the corner would say the dialog is
          busy while the text changed underneath it anyway.
        -->
        <Panel pad="bar">
        <AiGlow mode="overlay" :active="writing.running.value">
          <Editor
            ref="body"
            v-model="draft.content"
            :extensions="EXTENSIONS"
            format="html"
            :placeholder="__('Write your message')"
            :upload-function="uploadInline"
          >
            <template #default="{ editor }">
              <!--
                `flex-wrap`, which is the one thing between this row and a
                phone. Eleven controls do not fit 390px and the row does not
                scroll, so the last of them — the link, the picture, the table
                — were cut off the right edge with nothing to say they were
                there. Two rows of icons is what frappe-ui's own story does
                with the same menu, and it costs nothing at any width that
                already fitted.
              -->
              <EditorFixedMenu
                :editor="editor"
                :items="articleToolbar"
                class="mb-2 flex-wrap"
              />
              <!-- Taller in a pane, because a pane has the height: the box is
                   what somebody clicks into, so one sized for a dialog leaves
                   most of the column looking like it belongs to nothing. -->
              <EditorContent
                :editor="editor"
                :aria-label="__('Message')"
                dir="auto"
                :class="pane ? 'min-h-[12rem]' : ''"
              />
            </template>
          </Editor>
        </AiGlow>
        </Panel>

        <!--
          What just happened to the message, and the way back from it. A
          rewrite replaces the whole body, which is the one thing in this
          dialog somebody cannot get back by retyping — so the way back is
          offered rather than left to the editor's own undo, which by then is
          twenty transactions deep.
        -->
        <div
          v-if="writing.running.value || replaced !== null"
          class="flex items-center gap-2 text-p-xs text-ink-secondary"
          data-slot="mail-ai-strip"
        >
          <span v-if="writing.running.value">{{ __('Writing') }}</span>
          <span v-else>{{ __('Written by {0}. Read it before you send it.', [assistantName]) }}</span>
          <Button
            v-if="writing.running.value"
            variant="ghost"
            size="sm"
            :label="__('Stop')"
            @click="writing.stop()"
          />
          <Button
            v-else
            variant="ghost"
            size="sm"
            :label="__('Undo')"
            data-slot="mail-ai-undo"
            @click="undoWriting()"
          />
        </div>
        <ErrorMessage v-if="writing.error.value" :message="writing.error.value" />

        <!-- What is going with it. A forward arrives carrying the original's
             files; anything else is added below. -->
        <div v-if="draft.attachments.length" class="flex flex-wrap gap-2">
          <span
            v-for="one in draft.attachments"
            :key="one.name"
            class="flex items-center gap-1.5 rounded-6 border border-outline-gray-2 px-2 py-1 text-p-xs text-ink-secondary"
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
        :said="__('The message carries what the record says now, as text. It does not change afterwards.')"
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
  </ComposerFrame>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import {
  Button,
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
import ComposerFrame from '@/modules/onemail/components/ComposerFrame.vue'
import RecipientField from '@/modules/onemail/components/RecipientField.vue'
import AiGlow from '@/shared/components/AiGlow.vue'
import Panel from '@/shared/components/Panel.vue'
import RecordPanel from '@/shared/components/RecordPanel.vue'
import { useAiInsert } from '@/shared/lib/ai/insert'
import { useAiRun } from '@/shared/lib/ai/run'
import { withSignature } from '@/modules/onemail/components/signature'
import { mail } from '@/modules/onespace/lib/shell/mail'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import { workspace } from '@/shared/lib/workspace'
import { session } from '@/modules/onespace/lib/shell/session'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'
import { assistantName } from '@/modules/onespace/lib/shell/assistant'

const props = defineProps({
  /** The addresses this person may send from. The first is the default. */
  addresses: { type: Array, default: () => [] },
  /**
   * Drawn in the reading pane rather than as a dialog — `ComposerFrame.vue`
   * has the argument. OneMail passes it; a record's Mail tab does not, because
   * a record has no pane to draw one in.
   */
  pane: { type: Boolean, default: false },
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

// --- writing it, or fixing what is written ----------------------------------
//
// One run at a time and one target: the body. A rewrite replaces the whole
// message rather than a selection, and that is a decision rather than a
// shortcut — a selection in a rich-text editor is a ProseMirror range, the
// answer arrives as plain text over three seconds, and putting it back
// between two positions that move as it lands is a class of bug in exchange
// for a distinction nobody asked for in a five-line email.

const writing = useAiRun()

/** The body as it was before the last rewrite, or null. */
const replaced = ref(null)

/**
 * Plain text as paragraphs, escaped.
 *
 * The answer is plain text by contract — `ai/text.py` says why — so this is
 * the one place it becomes markup, and it escapes first: a model quoting a
 * customer called `Smith & Sons <UK>` must not arrive as a broken tag, which
 * is the same reason `put()` inserts a text node rather than a string.
 */
function asHtml(said) {
  const safe = (one) =>
    one.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return (said || '')
    .split(/\n{2,}/)
    .map((block) => `<p>${safe(block).replace(/\n/g, '<br>')}</p>`)
    .join('')
}

/**
 * The plain text of the body.
 *
 * What the assistant is told is in the message, when somebody has it open —
 * see `drafted` below. It was also what the composer's own verbs worked on,
 * and they have gone: the verbs are OneAI's now, and OneAI is a window over
 * this one rather than a button inside it.
 */
const bodyText = () =>
  new DOMParser().parseFromString(draft.content || '', 'text/html')
    .body.textContent.trim()

/**
 * What is being written, for the panel to be about.
 *
 * Exposed rather than claimed here: a claim belongs to whatever owns the
 * window, and `Mail.vue` is what knows which conversation this is a reply to
 * — one claim saying both, rather than two fighting over the same owner.
 * Empty while the composer is shut, so a thread nobody is answering is a
 * thread and not a draft.
 */
const drafted = computed(() => (open.value ? bodyText() : ''))

/**
 * Where an answer goes, while there is a message to put one in.
 *
 * The composer stopped drawing an AI button of its own — `Write with OneAI`
 * beside Attach a file was a second door to the thing the dock already opens,
 * and the writer's own button left the chrome for the same reason. What
 * replaces it is this: the panel draws **Insert** on an answer while this is
 * offering, and the words land in the message.
 *
 * Above what is there rather than at a cursor, because what is there is the
 * signature and the quoted history — the same place a suggested reply lands,
 * and the same offer to undo it.
 */
useAiInsert(() => {
  if (!open.value) return null
  return {
    label: __('this message'),
    insert(said) {
      const text = String(said || '').trim()
      if (!text) return false
      const before = draft.content
      draft.content = asHtml(text) + before
      replaced.value = before
      return true
    },
  }
})

/**
 * Run something that writes the message, and let it be taken back.
 *
 * One path for both the verbs and a suggested reply, because from the
 * message's point of view they are the same event: the body is replaced by
 * words nobody typed, over a few seconds, and there has to be a way back.
 *
 * `keep` is what a rewrite puts back on top of — a reply keeps the quoted
 * history and the signature underneath what arrives, and a rewrite replaces
 * everything.
 */
async function streamIntoBody(begin, { keep = '' } = {}) {
  if (writing.running.value) return

  const before = draft.content
  replaced.value = null

  // Set as it arrives rather than at the end. Assigning the model on each
  // flush is cheap and the editor is behind the overlay while it happens, so
  // there is no cursor to lose — and watching it land is the whole point.
  const stop = watch(writing.text, (said) => {
    if (said) draft.content = asHtml(said) + keep
  })

  try {
    await writing.start(begin)
  } finally {
    stop()
  }

  // Only where something actually landed: a run that was refused or failed
  // leaves the message exactly as it was, and offering to undo nothing is a
  // button that tells somebody their draft was touched when it was not.
  if (writing.text.value) replaced.value = before
  else draft.content = before
}

/**
 * Open as a reply and have one drafted into it.
 *
 * The composer opens first and empty, and the words arrive into it. Drafting
 * behind a spinner and opening with the answer already there would be the
 * same wait with nothing to watch — and it would put a finished letter in
 * front of somebody, which reads as a thing to send rather than a thing to
 * edit.
 */
async function suggestReply(from, thread, folder) {
  await compose(from, 'reply')
  // Everything the server's reply draft put in — the signature and the quoted
  // history — stays under what arrives.
  await streamIntoBody(
    () => workspace.mailSuggestReply(thread, folder),
    { keep: draft.content },
  )
}

function undoWriting() {
  if (replaced.value === null) return
  draft.content = replaced.value
  replaced.value = null
  writing.reset()
}

defineExpose({ compose, reopen, suggestReply, drafted })
</script>

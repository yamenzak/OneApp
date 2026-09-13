<template>
  <!--
    One document, open.

    The editor is frappe-ui's, which is tiptap with `RichTextKit` — tables,
    task lists, colour, alignment, slash commands and the rest. What is ours is
    everything around it: the save loop, the outline, the page settings, the
    history, and the fact that all of it hangs off a `File` rather than off a
    document store of its own.

    Reseamed from `frappe/writer` (AGPL-3.0, © Frappe Technologies). Their
    editor is the same tiptap with a Yjs provider under it, and their page is
    the same shape; what is not taken is the collaboration, because it needs a
    signalling server per shard. So this is one writer at a time, and the
    header says whose text is on screen and when it last landed.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <!-- The one editor bar, shared with the sheet — §E2/E3. What stood here
         was its earlier half: a `PageHeader` with the trail in it and a rename
         you had to open a dialog for. The trail, the mark, the title and the
         rename belong to the component now; what stays is what is true of a
         *document* — the outline, the writing verbs, and the three panels. -->
    <EditorChrome
      brand="onedoc"
      :crumbs="crumbs"
      :title="title"
      :placeholder="__('Untitled document')"
      :shared="shared"
      :renamable="!shared && writable"
      :hosted="hosted"
      @update:title="renameTo"
    >
      <template #status>
        <!-- Who else has this open. Before the save state rather than after
             it: "Saved a minute ago" is about the file and this is about the
             people, and the people are the thing you look for first when a
             sentence changes under you. -->
        <PresenceStrip :people="alsoHere" />
        <span class="text-p-xs text-ink-muted">{{ state }}</span>
      </template>

      <template #actions>
        <!-- The outline, on a phone. There is no room for a rail, and a reader
             thirty pages into a contract needs it more there than anywhere. -->
        <Dropdown v-if="worthShowing" :options="outlineOptions" class="lg:hidden">
          <Button
            variant="ghost"
            icon="lucide-list"
            :label="__('Outline')"
            :tooltip="__('Outline')"
          />
        </Dropdown>

        <!-- The verbs, in the header rather than in the formatting bar.
             The bar is bold, italic, a list — things that happen to a
             selection the instant they are clicked. These take seconds and
             cost credits, and the one that is not about a selection at all
             ("Write…") would be the odd item out among them.

             Not through a link: every endpoint behind it would refuse a
             guest, and a menu of things that answer "you cannot" is worse
             than no menu. -->
        <AiMenu
          v-if="!shared && writable && ai.live"
          :verbs="verbs"
          :busy="writing.running.value"
          :disabled="writing.running.value"
          :label="__('Write with {0}', [assistantName])"
          align="end"
          @ask="askAi"
        />

        <!-- The three controls that reach past this file, and the menu that
             does the same: the records it reads, what people have said about
             it, and what it looked like before. Each is a window onto the
             workspace and each of their endpoints would refuse a guest, so
             through a link there is the document and nothing else.

             Not on a phone — §D4. Six controls and a title do not fit at
             390px, and what happened instead was that they overlapped. So the
             three become entries in the menu below, which is where the sheet
             has always kept its own: the same verbs, one place, and nothing
             lost. `md:flex` and not `md:inline-flex`, because a `Button` is a
             flex row of icon and label. -->
        <Button
          v-if="!shared"
          class="hidden md:flex"
          variant="ghost"
          icon="lucide-link"
          :label="__('Records')"
          :tooltip="__('The records this document reads')"
          :class="showRecords ? 'bg-surface-gray-2' : ''"
          data-slot="records-toggle"
          @click="showRecords = !showRecords"
        />
        <Button
          v-if="!shared"
          class="hidden md:flex"
          variant="ghost"
          icon="lucide-message-square"
          :label="notes ? __('Notes ({0})', [notes]) : __('Notes')"
          :tooltip="__('What people have said about this document')"
          :class="showNotes ? 'bg-surface-gray-2' : ''"
          data-slot="notes-toggle"
          @click="showNotes = !showNotes"
        />
        <Button
          v-if="!shared"
          class="hidden md:flex"
          variant="ghost"
          icon="lucide-history"
          :label="__('Version history')"
          :tooltip="__('Version history')"
          :class="showHistory ? 'bg-surface-gray-2' : ''"
          @click="showHistory = !showHistory"
        />
        <Dropdown v-if="!shared" :options="menu">
          <Button
            variant="ghost"
            icon="lucide-more-horizontal"
            :label="__('What to do with this document')"
            :tooltip="__('What to do with this document')"
          />
        </Dropdown>
      </template>
    </EditorChrome>

    <div class="flex min-h-0 flex-1">
      <Outline :editor="editor" :revision="revision" />

      <div class="flex min-w-0 flex-1 flex-col">
        <!-- What was there before the last thing AI wrote, and the way back
             to it. Above the editor rather than floating over it: this is a
             statement about the document, and it has to stay readable while
             somebody scrolls through what arrived to decide. -->
        <div
          v-if="writing.running.value || replaced !== null || writing.error.value"
          class="flex shrink-0 flex-wrap items-center gap-2 border-b border-outline-gray-1 px-4 py-1.5"
          data-slot="doc-ai-strip"
        >
          <template v-if="writing.running.value">
            <AiGlow mode="inline" active>
              <span class="text-p-xs text-ink-secondary">{{ __('Writing…') }}</span>
            </AiGlow>
            <Button
              variant="ghost"
              size="sm"
              :label="__('Stop')"
              data-slot="doc-ai-stop"
              @click="writing.stop()"
            />
          </template>
          <template v-else-if="replaced !== null">
            <span class="text-p-xs text-ink-secondary">{{ __('Written by {0}. Check it.', [assistantName]) }}</span>
            <Button
              variant="ghost"
              size="sm"
              icon-left="lucide-undo-2"
              :label="__('Undo')"
              data-slot="doc-ai-undo"
              @click="undoWriting"
            />
          </template>
          <ErrorMessage v-if="writing.error.value" :message="writing.error.value" />
        </div>

        <!-- Not until `live.decided`. frappe-ui's `useEditor` decides
             collaboration mode from the extension list at construction, so an
             editor built a tick before the room answered would set its own
             content and then have the room's merged on top of it — the same
             paragraph twice. The wait is one socket round trip. -->
        <Editor
          v-if="liveReady"
          v-model="content"
          :extensions="liveExtensions"
          format="json"
          :editable="doc.can_write && !settings.locked"
          :upload-function="uploadInto"
          :placeholder="__('Start writing…')"
          @change="onChange"
          @transaction="onTransaction"
        >
          <template #default="{ editor: instance }">
            <!-- Captured so the outline, the word count and the print button
                 can read the same instance the person is typing into. -->
            {{ hold(instance) }}
            <EditorFixedMenu
              v-if="doc.can_write && !settings.locked"
              :editor="instance"
              :items="toolbar"
              class="shrink-0 overflow-x-auto overflow-y-hidden border-b border-outline-gray-1 px-4 py-1.5"
            />
            <EditorTableMenu v-if="doc.can_write" :editor="instance" />

            <!-- Paged, the scroller is a desk and the document is a stack
                 of sheets on it. Pageless, it is what it always was: prose in
                 the middle of the window with nothing behind it.

                 Two boxes rather than one, and the reason is dull but it cost
                 an afternoon: an absolutely positioned child is placed from
                 its parent's *padding* box, so a sheet that carried the page
                 margin as padding measured its blocks in one coordinate system
                 and drew its page breaks in another, one margin apart. The
                 sheet has no padding now. The column inside it does. -->
            <FadedScroll class="min-h-0 flex-1" :class="paper.paged ? 'bg-surface-gray-2' : ''">
              <div
                ref="sheet"
                :data-paper="paperId"
                class="relative mx-auto"
                :class="paper.paged ? 'doc-sheet my-8 shadow-raised' : 'w-full'"
                :style="sheetStyle"
              >
                <template v-if="paper.paged">
                  <!-- What makes two sheets two sheets: the desk showing
                       between them, edge to edge. -->
                  <div
                    v-for="(top, index) in pages.tops.slice(1)"
                    :key="`gap-${index}`"
                    class="pointer-events-none absolute inset-x-0 bg-surface-gray-2"
                    :style="{ top: `${top - paper.gap}px`, height: `${paper.gap}px` }"
                    aria-hidden="true"
                  />
                  <!--
                    The letter head at the top of every page after the first.

                    The first one is in the flow below, because only the first
                    can be: the rest sit in space `paginate()` has already left
                    for them, which is how a repeat can be exact rather than a
                    guess. Subtle in both, because it is not content and it is
                    not editable and it should not read as either.
                  -->
                  <div
                    v-for="(top, index) in headMarkup ? pages.tops.slice(1) : []"
                    :key="`head-${index}`"
                    class="pointer-events-none absolute select-none border-b border-outline-gray-2 pb-3 opacity-60"
                    :style="headStyle(top)"
                    aria-hidden="true"
                    v-html="headMarkup"
                  />
                </template>

                <div
                  ref="columnEl"
                  :class="paper.paged ? '' : ['mx-auto px-6 py-10', ...pageClasses(settings)]"
                  :style="columnStyle"
                >
                  <!-- `v-html` because `Letter Head.validate` scrubs the markup
                       on the way in — the same reason the settings screen
                       renders its preview this way. -->
                  <div
                    v-if="paper.paged && headMarkup"
                    ref="headEl"
                    class="pointer-events-none mb-6 select-none border-b border-outline-gray-2 pb-3 opacity-60"
                    aria-hidden="true"
                    v-html="headMarkup"
                  />
                  <EditorContent
                    :editor="instance"
                    :aria-label="__('Document')"
                    dir="auto"
                    class="prose prose-sm max-w-none"
                    :style="paper.paged ? typeStyle(settings) : {}"
                  />
                </div>
              </div>
            </FadedScroll>
          </template>
        </Editor>

        <footer
          class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-gray-1 px-4 py-1.5 text-p-xs text-ink-muted"
        >
          <span>{{ counted }}</span>
          <span v-if="settings.locked" class="flex items-center gap-1">
            <Icon name="lucide-lock" class="size-3" />
            {{ __('Locked — unlock it from the menu to type') }}
          </span>
        </footer>
      </div>

      <RecordPanel
        v-if="showRecords"
        :name="name"
        :sources="sources"
        :values="said"
        :busy="asking"
        :read-at="readAt"
        :said="__('The document will read this record. Every field you have already put in the prose fills itself in.')"
        :can-write="doc.can_write && !settings.locked"
        :suggestions="suggested"
        @insert-field="insertField"
        @insert-table="insertTable"
        @used="readSuggestions"
        @refresh="readRecords"
        @changed="sources = $event"
        @close="showRecords = false"
      >
        <!-- The one thing only a document can do with what it just read:
             stop asking. A quotation the customer received is a fact about a
             day, not a view onto a record that has moved on. -->
        <template #footer="{ rows }">
          <Button
            v-if="doc.can_write && !settings.locked && rows.length"
            variant="ghost"
            size="sm"
            :label="__('Fix the fields')"
            :tooltip="__('Stop asking, and keep what they say now')"
            data-slot="fields-settle"
            @click="settle"
          />
        </template>
      </RecordPanel>

      <FileChat
        v-if="showNotes"
        :name="name"
        @count="notes = $event"
        @close="showNotes = false"
      />

      <VersionPanel
        v-if="showHistory"
        :file="name"
        kind="Doc"
        :can-write="doc.can_write"
        :revision="saved"
        @close="showHistory = false"
        @preview="preview"
        @restored="reopen"
      />
    </div>

    <!--
      The one AI action that asks before it runs. Everything else here adds
      to the document or changes a selection; this replaces the whole thing,
      so it says so, takes an optional brief, and leaves Undo one press away
      afterwards.
    -->
    <Dialog v-model="filling" :title="__('Fill in this document')">
      <template #default>
        <div class="flex flex-col gap-3">
          <p class="text-p-sm text-ink-secondary">
            {{ outlineCount
              ? __('It writes under each of the {0} headings, from the records this document reads. Undo brings it back.', [outlineCount])
              : __('No headings yet, so say what it should say. Undo brings back what is here now.') }}
          </p>
          <FormControl
            v-model="fillBrief"
            type="textarea"
            :rows="3"
            :label="__('Anything else it should know')"
            :placeholder="__('A fixed-price quotation for the cladding, addressed to the consultant.')"
            data-slot="doc-fill-brief"
          />
        </div>
      </template>
      <template #actions>
        <Button
          variant="solid"
          :label="__('Write it')"
          :disabled="!outlineCount && !fillBrief.trim()"
          data-slot="doc-fill-go"
          @click="fillDocument"
        />
      </template>
    </Dialog>

    <DocSettings v-model="showSettings" v-model:settings="settings" @change="save()" />

    <TemplatePicker
      v-model="picking"
      :rows="templates"
      icon="lucide-file-signature"
      :said="__('This opens the template as a new document. What you have here is not touched.')"
      @pick="fromTemplate"
    />

    <Dialog v-model="showing" :title="shown?.title || __('An earlier version')" size="3xl">
      <template #default>
        <!--
          The same editor, not editable, rather than the stored HTML through
          `v-html`. Two reasons and the second is the real one: a version holds
          ProseMirror JSON, so rendering it any other way would mean a second
          renderer to keep in step with the first — and a document is text
          somebody in this workspace wrote, which is exactly the text nobody
          should be pasting into an `innerHTML`.
        -->
        <Editor
          v-if="shownContent"
          :model-value="shownContent"
          :extensions="READING"
          format="json"
          :editable="false"
        >
          <template #default="{ editor: reading }">
            <EditorContent
              :editor="reading"
              class="prose prose-sm max-h-[60vh] max-w-none overflow-auto"
              dir="auto"
            />
          </template>
        </Editor>
        <Skeleton v-else class="h-40 w-full" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, useId, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  Button,
  Dialog,
  Dropdown,
  Editor,
  EditorContent,
  EditorFixedMenu,
  EditorTableMenu,
  ErrorMessage,
  FormControl,
  Icon,
  RichTextKit,
  Skeleton,
} from '@/ui'
import FadedScroll from '@/shared/components/FadedScroll.vue'
import FileChat from '@/shared/components/FileChat.vue'
import PresenceStrip from '@/shared/components/PresenceStrip.vue'
import DocSettings from '@/modules/onedoc/components/DocSettings.vue'
import RecordPanel from '@/shared/components/RecordPanel.vue'
import {
  RecordField,
  RecordTable,
  applyRecordFields,
  applyRecordTables,
  namedFields,
} from '@/modules/onedoc/lib/recordField'
import Collaboration from '@tiptap/extension-collaboration'
import CollaborationCaret from '@tiptap/extension-collaboration-caret'

import AiGlow from '@/shared/components/AiGlow.vue'
import AiMenu from '@/shared/components/AiMenu.vue'
import Outline from '@/modules/onedoc/components/Outline.vue'
import VersionPanel from '@/modules/onespace/components/versions/VersionPanel.vue'
import TemplatePicker from '@/modules/onestorage/components/TemplatePicker.vue'
import EditorChrome from '@/shared/components/EditorChrome.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { documentToolbar, liveDocumentToolbar, pageClasses } from '@/modules/onedoc/components/toolbar'
import { geometry, typeStyle } from '@/shared/lib/paper/setup'
import { paginate } from '@/shared/lib/paper/paginate'
import { printHtml } from '@/shared/lib/paper/print'
import { asProse } from '@/modules/onedoc/lib/prose'
import { useAiRun } from '@/shared/lib/ai/run'
import { writingVerbs } from '@/shared/lib/ai/verbs'
import { useLiveDocument } from '@/modules/onedoc/lib/live'
import { useOutline } from '@/shared/composables/useOutline'
import { throughLink } from '@/shared/lib/live/link'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { putFile } from '@/modules/onestorage/lib/attach'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'
import { notifyWarning } from '@/shared/lib/runtime/notify'
import { assistantName } from '@/modules/onespace/lib/shell/assistant'

const route = useRoute()

const props = defineProps({
  name: { type: String, required: true },
  doc: { type: Object, required: true },
  /**
   * Inside the Drive's pane rather than on a page of its own.
   *
   * It changes where the bar goes: `PageHeader` is a teleport into the shell's
   * header, so a hosted editor that drew one would put its title above the
   * file list it is sitting beside rather than above itself.
   */
  hosted: { type: Boolean, default: false },
})

const emit = defineEmits(['renamed', 'reload'])

// Opened through `/one/link/<secret>` rather than from inside the workspace.
// Read off the address bar rather than taken as a prop, for the reason
// `shared/lib/live/link.js` gives: the secret is already there, it cannot
// disagree with itself, and the same file's save reads it the same way.
const shared = throughLink()

// Which half of the bar this is — `lib/shell/breakpoint.js`, the one number.
const phone = useIsMobile()

// The whole capability of the editor. RichTextKit is frappe-ui's article-grade
// bundle, which is the right one for a document — the lighter CommentKit is
// built for a box inside a form. Beside it, the two nodes that are ours: a
// field of one of the records this document reads, and a child table of one.
// Both are names rather than text, and both are rendered from the record on
// every read — `lib/recordField.js`.
function extensionsFor(collab) {
  if (!collab) return [RichTextKit, RecordField, RecordTable]
  return [
    // Collaboration brings its own undo, scoped to what *this* person did —
    // and it cannot coexist with the kit's, which would undo a colleague's
    // sentence because it was the last thing that happened.
    RichTextKit.configure({ starterKit: { undoRedo: false } }),
    RecordField,
    RecordTable,
    Collaboration.configure({ document: collab.document }),
    // The extension wants a Hocuspocus provider and uses exactly one thing
    // off it, so it gets exactly that thing.
    CollaborationCaret.configure({ provider: { awareness: collab.awareness } }),
  ]
}

// The version preview renders stored JSON and must never be collaborative:
// it is a second editor on the same page, and a second binding to the same
// Y.Doc would make reading an old version type it back into the current one.
const READING = extensionsFor(null)

// Which row of controls. The only difference is undo and redo — see
// `toolbar.js` — and it is decided by whether the editor is collaborative,
// which is the same thing `liveExtensions` decided.
const toolbar = computed(() => (room.value ? liveDocumentToolbar : documentToolbar))

const {
  decided: liveReady,
  room,
  extensions: liveExtensions,
  people: alsoHere,
  stop: stopLive,
} = useLiveDocument({
  name: props.name,
  initial: props.doc.content ? JSON.parse(props.doc.content) : null,
  build: extensionsFor,
})

//: How long after the last keystroke a save goes out. Long enough that typing
//: a sentence is one save; short enough that closing the tab mid-thought loses
//: at most this.
const QUIET_MS = 1200

const title = ref(props.doc.title || '')
const content = ref(props.doc.content ? JSON.parse(props.doc.content) : null)
const settings = ref({ ...(props.doc.settings || {}) })

// Whether the document was unsaved before the tokens were patched. The two
// events around the patch arrive in one tick, so a keystroke cannot land
// between them and be forgotten. See `RecordPanel.vue`.
const wasDirty = ref(false)

// The records this document reads — `Bound Record` rows, keyed, so a token
// names `key.field` and the record behind a key can be swapped without
// touching the prose. See `shared/binding.py`.
const sources = ref([...(props.doc.sources || [])])

// The rail is open when there is something in it. A document about nothing
// is most of them, and a panel saying so on every open would be a panel
// everybody closes.
const showRecords = ref(!!(props.doc.sources || []).length)

// Whether the document was unsaved before the tokens were patched — see
// `readRecords`. Declared here because both it and `dirty` are read in one
// tick and a keystroke must not land between them.

/**
 * The document after its tokens were fixed — no longer names, now words.
 *
 * Taken from the server's answer rather than patched here, because freezing
 * changes every token at once and the JSON it wrote is what is on disk. Not
 * dirty afterwards: the save that produced it has already landed, and marking
 * it otherwise would send the same body back a second later.
 */
function refreshed(next) {
  if (!next) return
  content.value = JSON.parse(next)
  dirty.value = false
}

/*
 * What the records say, and when they were asked.
 *
 * Here rather than in the rail because it is the *document's* answer: the
 * tokens in the prose are what gets patched with it, the rail only draws it
 * as a preview beside each field. `shared/components/RecordPanel.vue`.
 */
const said = ref({})
const asking = ref(false)
const readAt = ref(null)

async function readRecords() {
  asking.value = true
  try {
    // What is in the editor, not what is on disk: the save is debounced, and
    // a token somebody inserted a second ago is only in the editor.
    const answer = await workspace.docFields(props.name, namedFields(editor.value))
    said.value = answer?.fields || {}
    if (answer?.sources) sources.value = answer.sources
    // Bracketed, and the two have to stay in the same tick: patching is a
    // ProseMirror transaction, the editor calls that a change, and a change
    // starts the save loop. Opening a document would then write it — a new
    // body and a new version on every open, none of it anything a person did.
    wasDirty.value = dirty.value
    applyRecordFields(editor.value, said.value)
    applyRecordTables(editor.value, answer?.tables || {})
    dirty.value = wasDirty.value
    readAt.value = new Date()
  } finally {
    asking.value = false
  }
}

/*
 * Insert first, focus after — and never `focus()` inside the chain. The
 * reason cost an afternoon.
 *
 * Tiptap's `focus` command builds a transaction, calls `view.focus()`, and
 * then dispatches. From a control *inside* the editor that is fine, because
 * the prose already had focus and nothing happens in between. From the rail
 * it is not: the click moved focus out, so `view.focus()` really does move it
 * back, the browser fires a selection change, ProseMirror dispatches for it —
 * and the command is left holding a transaction against a document that has
 * moved. "Applying a mismatched transaction", and nothing inserted.
 */
function put(run) {
  const instance = editor.value
  if (!instance) return
  run(instance.commands)
  instance.view?.focus()
  // Straight away, so the token shows a number rather than an em dash for as
  // long as it takes somebody to notice.
  readRecords()
}

const insertField = (one) => put((commands) => commands.insertRecordField({
  source: one.source, field: one.field, label: one.label,
  text: one.text || undefined,
}))

const insertTable = (one) => put((commands) => commands.insertRecordTable({
  source: one.source, table: one.table, label: one.label, columns: one.columns,
}))

async function settle() {
  const answer = await workspace.docSettleFields(props.name)
  refreshed(answer?.content)
}

// --- what a model writes into this document ---------------------------------
//
// Three shapes and one composable. The verbs replace a selection, Write…
// puts a passage at the cursor, and Fill in replaces the document — and all
// three arrive the same way, into the prose, where somebody watches them land
// rather than waiting behind a spinner and being handed a result.
//
// Nothing here saves. What arrives is a ProseMirror transaction like any
// other, so the ordinary debounced save takes it a second later and Undo is
// the editor's own history plus the strip above — which is what makes
// replacing a whole document a safe thing to offer.

const ai = writingVerbs()
const writing = useAiRun()

//: What the menu offers here. No `summarise`: the document is on screen, and
//: a summary of what somebody is looking at belongs in mail, where the thing
//: being summarised is forty messages long.
const verbs = ['write', 'improve', 'proofread', 'shorten', 'expand', 'tone']

const writable = computed(() => props.doc.can_write && !settings.value.locked)

/** What the document said before the last thing AI wrote, or `null`. */
const replaced = ref(null)

/**
 * Stream an answer into a range of the prose.
 *
 * Re-inserted on every flush rather than appended, and that is the whole
 * trick: `insertContentAt` over the range the last flush produced replaces
 * it, so the text grows in place and ProseMirror keeps one undo step per
 * flush instead of one per token. `asProse` is what turns the plain text the
 * prompts ask for into blocks — see `lib/prose.js`.
 */
async function streamInto(begin, { from, to, headings = [] } = {}) {
  const instance = editor.value
  if (!instance || writing.running.value) return

  const before = instance.getHTML()
  replaced.value = null

  const start = from ?? instance.state.selection.from
  let end = to ?? instance.state.selection.to

  const stop = watch(writing.text, (said) => {
    if (!said) return
    const html = asProse(said, headings)
    instance.commands.insertContentAt({ from: start, to: end }, html)
    // Where the next flush has to replace from. Read back off the document
    // rather than counted from the string: what was inserted is what
    // ProseMirror parsed, and its length is a node count, not a character
    // count.
    end = instance.state.selection.to
  })

  try {
    await writing.start(begin)
  } finally {
    stop()
  }

  // Only where something landed. A run that was refused or failed leaves the
  // prose exactly as it was, and offering to undo nothing tells somebody
  // their document was touched when it was not.
  if (writing.text.value) replaced.value = before
  else instance.commands.setContent(before, false)
}

/** One of the verbs, from the menu. */
function askAi(ask) {
  const instance = editor.value
  if (!instance) return

  if (ask.verb === 'write') {
    streamInto(() => workspace.docWrite(props.name, ask.instruction))
    return
  }

  const { from, to } = instance.state.selection
  const said = instance.state.doc.textBetween(from, to, '\n\n')
  if (!said.trim()) {
    // Said here rather than refused at the endpoint, because the endpoint
    // cannot see a selection and this is the one thing it would be wrong
    // about.
    writing.reset()
    notifyWarning(__('Select the words to work on first.'))
    return
  }
  streamInto(() => workspace.docRewrite(props.name, { ...ask, text: said }),
             { from, to })
}

/**
 * Write out the whole document from its own headings.
 *
 * The largest thing AI does anywhere in this product, so it says what it will
 * do before it does it and leaves one press between the person and the way
 * back. The headings are read from the editor rather than from the server,
 * for the reason `readRecords` reads the editor: the save is debounced, and a
 * heading typed a second ago is only here.
 */
async function fillDocument() {
  const instance = editor.value
  if (!instance) return
  const said = headings.value.map((one) => one.text)
  filling.value = false
  await streamInto(
    () => workspace.docFill(props.name, fillBrief.value.trim()),
    { from: 0, to: instance.state.doc.content.size, headings: said },
  )
  fillBrief.value = ''
}

const filling = ref(false)
const fillBrief = ref('')

//: How many headings there are to write under. What the dialog says, and
//: whether a brief is required: a document with no headings and no brief is
//: an instruction to write nothing in particular.
const outlineCount = computed(() => headings.value.length)

function undoWriting() {
  if (replaced.value === null) return
  editor.value?.commands.setContent(replaced.value, true)
  replaced.value = null
  writing.reset()
}

// --- and which records it should be reading ---------------------------------
//
// Retrieval, not a ranking: `onedoc/intelligence.suggest_sources` embeds the
// prose and hands back the nearest records this reader can open, and the
// person picks one. Asked when the panel opens rather than on every keystroke
// — an embedding is a metered call, and a document does not change what it is
// about between two sentences.

const suggested = ref([])

async function readSuggestions() {
  if (shared || !writable.value) return
  suggested.value = (await workspace.docSuggestedSources(props.name).catch(() => [])) || []
}

watch(showRecords, (open) => { if (open) readSuggestions() })

/*
 * The live tiptap instance — `shallowRef`, and that is load-bearing.
 *
 * A plain `ref` deep-wraps what it holds in `reactive()`, so everything read
 * through it comes back as a Proxy. A command run against the proxy builds
 * its transaction from a *proxied* document, ProseMirror compares that
 * against the real one on the way in, and every insert from outside the
 * editor fails with "Applying a mismatched transaction". Nothing here wants
 * the editor's internals to be reactive anyway: `revision` is what the
 * outline and the word count recompute on.
 */
const editor = shallowRef(null)
const revision = ref(0)
const dirty = ref(false)
const busy = ref(false)
const failed = ref('')
const savedAt = ref(props.doc.modified || '')
// Bumped after every landed save, so the history panel follows the work.
const saved = ref(0)

/*
 * Paper.
 *
 * `paper` is the same resolution `shared/paper.py` does on the way out,
 * so what the sheet on screen is is what the printer gets. `headMarkup` is the
 * chosen letter head's HTML, fetched once when a document that has one opens —
 * a document with no letter head, which is most of them, asks for nothing.
 */
const paper = computed(() => geometry(settings.value))
const headMarkup = ref('')

const sheet = ref(null)
const headEl = ref(null)
const columnEl = ref(null)

/*
 * The pushes are written into a stylesheet of this sheet's own, and the
 * attribute is how a rule finds it. `useId` rather than a counter because two
 * documents can be open at once — a record's pane and the file behind it.
 */
const paperId = useId()
let rules = null
const pages = ref({ pages: 1, tops: [0], height: 0 })

/*
 * Where the pages break, measured rather than drawn.
 *
 * A hairline every page height was a guide and this is the thing itself: the
 * blocks are laid out, the first one that would not fit is pushed onto the
 * next page, and the letter head is drawn at the top of every page that
 * results. It agrees with the printed page because the same engine lays the
 * same blocks out at the same width in the same type — `docs/typography.py`
 * is the other half of that, and `lib/paper/paginate.js` is this half.
 */
function repaginate() {
  if (!paper.value.paged || !sheet.value) return
  const body = sheet.value.querySelector('.ProseMirror')
  if (!body) return

  // The letter head is above the text on every page, so what it takes is what
  // every page has less of. Its margin counts: it is the gap to the first
  // paragraph, and that gap is on every page too.
  const mark = headEl.value
  const height = mark
    ? mark.offsetHeight + parseFloat(getComputedStyle(mark).marginBottom || 0)
    : 0

  if (!rules) {
    rules = document.createElement('style')
    document.head.append(rules)
  }

  pages.value = paginate(
    sheet.value, body, rules, `[data-paper="${paperId}"] .ProseMirror`,
    paper.value, height,
  )
}

/** After the DOM has settled, and never twice in one frame. */
let pending = null
function schedule() {
  if (pending) return
  pending = requestAnimationFrame(() => {
    pending = null
    repaginate()
  })
}

/*
 * Anything that changes a height changes where the pages break, and most of
 * those are not transactions. The letter head's logo is the one that cost an
 * afternoon: it was measured before the image had loaded, so every page after
 * the first was laid out about a hundred pixels short and the repeated letter
 * head landed in the middle of a paragraph. A web font arriving does the same
 * thing more quietly.
 *
 * Watching the boxes rather than the causes: one observer over the letter head
 * and the prose. It settles after one extra pass, because a second run on an
 * unchanged layout produces the same margins and so no further resize.
 */
let watcher = null
function watchSizes() {
  if (!window.ResizeObserver || !sheet.value) return
  watcher?.disconnect()
  watcher = new ResizeObserver(schedule)
  // The column, not the prose: the letter head is the thing that changes
  // height when its logo arrives, and it is the prose's *sibling*. Watching
  // the prose sees a box that moved rather than one that grew, and a box that
  // moved fires nothing.
  if (columnEl.value) watcher.observe(columnEl.value)

  // And the images by name, because a letter head is usually a logo and an
  // `<img>` with no width attribute is nothing at all until it has loaded.
  // Measuring the page against a letter head that is about to get a hundred
  // pixels taller is how every page after the first ends up wrong.
  for (const img of sheet.value.querySelectorAll('img')) {
    if (img.complete) continue
    img.addEventListener('load', schedule, { once: true })
    img.addEventListener('error', schedule, { once: true })
  }
}

const sheetStyle = computed(() => {
  if (!paper.value.paged) return {}
  return {
    width: `${paper.value.width}mm`,
    maxWidth: '100%',
    // Tall enough for the last page to be a whole page. A paged document that
    // stops where the words stop is the pageless one with a border round it.
    minHeight: `${pages.value.height || paper.value.pageHeight}px`,
  }
})

/** The text column: the page's margins, and nothing else. */
const columnStyle = computed(() =>
  (paper.value.paged ? { padding: `${paper.value.margin}mm` } : {}),
)

const headStyle = (top) => ({
  top: `${top + paper.value.marginPx}px`,
  left: `${paper.value.marginPx}px`,
  right: `${paper.value.marginPx}px`,
})

// Every reason the pages could move: the text changed, the page setup changed,
// the letter head arrived, the window got narrower.
watch(revision, schedule)
watch(columnEl, watchSizes)
watch([() => settings.value, headMarkup], schedule, { deep: true })
onMounted(() => {
  schedule()
  nextTick(watchSizes)
  window.addEventListener('resize', schedule)
  // A face that arrives late re-measures everything it sets.
  document.fonts?.ready?.then(schedule)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', schedule)
  watcher?.disconnect()
  rules?.remove()
})

watch(
  () => [paper.value.paged, paper.value.letterHead],
  async ([paged, head]) => {
    if (!paged || !head) return (headMarkup.value = '')
    try {
      headMarkup.value = (await workspace.letterHead(head))?.content || ''
      await nextTick()
      watchSizes()
      schedule()
    } catch {
      // A letter head somebody deleted is a document that prints without one,
      // which is what `paper.letter_head_html` decides on the server too.
      headMarkup.value = ''
    }
  },
  { immediate: true },
)

const showHistory = ref(false)

// The conversation about the document, as opposed to the one in it. Closed
// on open like the other rails — a document nobody has said anything about
// is most of them, and a panel saying so on every open is a panel everybody
// closes. The count on the button is what says there is something to read.
const showNotes = ref(false)
const notes = ref(0)

// Asked once on open, so the button can say there is something to read
// before anybody presses it. The panel keeps it in step after that. Not
// through a link: there is no button to label, and the endpoint would refuse
// a guest anyway.
if (!shared) {
  workspace.driveNotes(props.name)
    .then((answer) => { notes.value = answer?.count || 0 })
    .catch(() => {})
}
const showSettings = ref(false)

/*
 * Templates, and what picking one does.
 *
 * Fetched when the menu is first opened rather than on mount: most documents
 * are opened to read, and a query for a list nobody will look at is a query
 * every open pays for.
 */
const router = useRouter()
const picking = ref(false)
const templates = ref([])

watch(picking, (open) => {
  if (!open || templates.value.length) return
  workspace.docTemplates()
    .then((found) => { templates.value = found || [] })
    .catch(() => { templates.value = [] })
})

/*
 * Starting from a template.
 *
 * No record is asked for here, and that is the change: a template hands over
 * its *slots* — "a quotation goes here" — and the document opens with them
 * empty and the rail prompting for each. Asking in a dialog first was one
 * question and one answer, and the thing people actually want is to fill in
 * the quotation the template named and then add the customer it did not.
 */
async function fromTemplate(row) {
  const made = await workspace.docMake({
    template: row.name,
    title: __('{0} copy', [row.file_name]),
  })
  router.push({ name: 'Doc', params: { name: made.name } })
}
const showing = ref(false)
const shown = ref(null)
const shownContent = ref(null)

let timer = null

/** Keep the live editor instance where the outline and the counter can read it. */
function hold(instance) {
  if (instance && editor.value !== instance) editor.value = instance
  return ''
}

function onTransaction() {
  revision.value += 1
}

// The same headings the rail draws, for the phone's dropdown. One computation,
// two surfaces.
const { headings, worthShowing, go } = useOutline(editor, revision)

const outlineOptions = computed(() =>
  headings.value.map((one) => ({
    label: one.text,
    icon: one.level > 2 ? 'lucide-minus' : 'lucide-hash',
    onClick: () => go(one),
  })),
)

function onChange() {
  if (!props.doc.can_write) return
  dirty.value = true
  failed.value = ''
  clearTimeout(timer)
  timer = setTimeout(() => save(), QUIET_MS)
}

const state = computed(() => {
  if (failed.value) return failed.value
  if (busy.value) return __('Saving…')
  if (dirty.value) return __('Unsaved')
  if (!savedAt.value) return ''
  return __('Saved {0}', [ago(savedAt.value)])
})

const counted = computed(() => {
  void revision.value
  const text = editor.value?.state?.doc?.textContent || ''
  const words = text.trim() ? text.trim().split(/\s+/).length : 0
  return words === 1 ? __('{0} word', [words]) : __('{0} words', [words])
})

async function save() {
  if (!props.doc.can_write || busy.value) return
  clearTimeout(timer)

  const instance = editor.value
  if (!instance) return

  busy.value = true
  try {
    const answer = await workspace.docSave(props.name, {
      content: JSON.stringify(instance.getJSON()),
      html: instance.getHTML(),
      title: title.value,
      settings: JSON.stringify(settings.value),
    })
    dirty.value = false
    savedAt.value = new Date().toISOString()
    saved.value = answer?.head_seq ?? saved.value + 1
    emit('renamed', title.value)
  } catch (raised) {
    // Beside the title rather than in a toast: a save that failed is a fact
    // about the document on screen, and the person is looking at it.
    failed.value = raised?.messages?.[0] || __('Could not save')
  } finally {
    busy.value = false
  }
}

/** An image dropped or pasted into the prose becomes a file in the Drive.
 *  The same funnel every other upload goes through, so a picture in a document
 *  is in the storage meter and in the bin like anything else. */
const uploadInto = (file) => putFile(file, { folder: props.doc.folder || '' })

async function preview(one) {
  shown.value = one
  shownContent.value = null
  showing.value = true

  const answer = await workspace.fileVersionBody(one.name, 'Doc')
  try {
    shownContent.value = JSON.parse(answer?.payload || 'null')
  } catch {
    shownContent.value = null
  }
}

function reopen() {
  showing.value = false
  emit('reload')
}

/**
 * Files, and nothing after it — §C1.
 *
 * The root used to be `back` *or* Files, so the same document had a different
 * first crumb depending on how you reached it, and there was no way home from
 * one opened off a record. Then it was Files *and* where you came from, which
 * was better and still two lines of route above a document. `Trail` collapses
 * a trail that draws a subject, and the subject here is the title: what a
 * person wants over an open document is its name and one press out.
 */
const crumbs = useCrumbs({ label: __('Files'), route: { name: 'Drive' } })

/*
 * The title, as typed into the bar.
 *
 * It was a dialog off the menu, in the Drive's shape, and the sheet's was an
 * input you clicked into — which is what a person who has used a spreadsheet
 * expects of a title beside a mark. `EditorChrome` carries the sheet's, so
 * this is the half that lands it: one save, the same one every keystroke in
 * the body goes through.
 */
async function renameTo(next) {
  title.value = next
  await save()
}

const isTemplate = ref(!!props.doc.is_template)

/*
 * What to do with this document.
 *
 * Grouped, and in the order the sheet's own menu uses — Export, then what
 * this file *is*. The two editors are one suite and the verbs are nearly the
 * same verbs; a flat list here and three groups there made them read as two
 * products that happened to ship together. `docs/WRITER.md` §7.
 */
const menu = computed(() => [
  { group: __('Export'), options: [
    {
      // The page the server builds, printed from a frame of its own — the
      // size, the margins and the letter head on every sheet are all in that
      // page and none of them are in this window. `lib/paper/print.js`.
      label: __('Print'),
      icon: 'lucide-printer',
      onClick: async () => {
        if (dirty.value) await save()
        const found = await workspace.docPrintable(props.name)
        if (found?.html) await printHtml(found.html)
      },
    },
    {
      label: __('Download as HTML'),
      icon: 'lucide-download',
      onClick: () => {
        window.location.href =
          `/api/method/oneapp.onedoc.download?name=${encodeURIComponent(props.name)}`
      },
    },
    {
      // Beside Copy, not instead of it: one is for pasting into a chat and
      // one is for handing somebody a file.
      label: __('Download as Markdown'),
      icon: 'lucide-file-down',
      onClick: () => {
        window.location.href =
          `/api/method/oneapp.onedoc.download_markdown?name=${encodeURIComponent(props.name)}`
      },
    },
    {
      label: __('Copy as Markdown'),
      icon: 'lucide-clipboard',
      onClick: async () => {
        const answer = await workspace.docMarkdown(props.name)
        await navigator.clipboard.writeText(answer?.markdown || '')
      },
    },
  ]},
  // The three panel toggles, where a phone can reach them — §D4. They are
  // buttons on the bar at `md:` and up and hidden below it, so this group is
  // their only door at 390px; `condition` rather than a second menu, because
  // one list that knows the width is one list.
  { group: __('Open beside this'), options: [
    {
      label: showRecords.value ? __('Hide the records') : __('Records'),
      icon: 'lucide-link',
      condition: () => phone.value,
      onClick: () => { showRecords.value = !showRecords.value },
    },
    {
      label: notes.value ? __('Notes ({0})', [notes.value]) : __('Notes'),
      icon: 'lucide-message-square',
      condition: () => phone.value,
      onClick: () => { showNotes.value = !showNotes.value },
    },
    {
      label: __('Version history'),
      icon: 'lucide-history',
      condition: () => phone.value,
      onClick: () => { showHistory.value = !showHistory.value },
    },
  ]},
  { group: __('This document'), options: [
    {
      // Where a template is reached from, now that it is not in the New menu.
      // A blank page is when you realise you wanted one, and a new document
      // is what it opens — this one is left exactly as it was, which is the
      // whole reason it is not called "apply".
      label: __('Load a template'),
      icon: 'lucide-bookmark',
      onClick: () => { picking.value = true },
    },
    {
      // Here rather than in the AI menu beside the verbs. The verbs act on
      // what is selected and this replaces the document — putting it one
      // item under "Improve" is how somebody loses an afternoon's writing to
      // a misread menu.
      label: __('Fill in this document'),
      icon: 'lucide-sparkles',
      condition: () => !shared && writable.value && ai.live,
      onClick: () => { fillBrief.value = ''; filling.value = true },
    },
    {
      label: __('Page setup'),
      icon: 'lucide-settings-2',
      onClick: () => { showSettings.value = true },
    },
    {
      label: settings.value.locked ? __('Unlock') : __('Lock against typing'),
      icon: settings.value.locked ? 'lucide-unlock' : 'lucide-lock',
      condition: () => props.doc.can_write,
      onClick: () => {
        settings.value = { ...settings.value, locked: !settings.value.locked }
        save()
      },
    },
    {
      label: __('Duplicate'),
      icon: 'lucide-copy',
      onClick: () => workspace.docDuplicate(props.name, __('{0} copy', [title.value])),
    },
    {
      // A template is a document with a flag on it, so this is the whole
      // feature — see `onedoc/templates.py`. It then appears in the New menu,
      // in the Drive and on a record's Files tab alike.
      label: isTemplate.value ? __('Stop using as a template') : __('Use as a template'),
      icon: isTemplate.value ? 'lucide-bookmark-minus' : 'lucide-bookmark-plus',
      condition: () => props.doc.can_write,
      onClick: async () => {
        const next = !isTemplate.value
        await workspace.docSetTemplate(props.name, next)
        isTemplate.value = next
      },
    },
  ]},
])

// A save the moment the page goes away, because the quiet timer has not fired
// yet and the last sentence is the one worth keeping.
watch(() => props.doc, (next) => {
  title.value = next.title || ''
  isTemplate.value = !!next.is_template
  sources.value = [...(next.sources || [])]
  showRecords.value = !!(next.sources || []).length
  content.value = next.content ? JSON.parse(next.content) : null
  settings.value = { ...(next.settings || {}) }
  dirty.value = false
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  if (dirty.value) save()
  // After the save, not before: leaving the room destroys the provider, and
  // the provider's teardown flushes the last burst of typing at the people
  // still in it. A save that ran after would be saving the same thing.
  stopLive()
})
</script>

<style scoped>
/*
 * Somebody else's caret.
 *
 * Tiptap's caret extension draws the elements and ships no CSS for them —
 * `render(user)` builds a `<span class="collaboration-carets__caret">` with a
 * `<div class="collaboration-carets__label">` inside it, sets the two colours
 * inline, and leaves the geometry to whoever is using it. Without this the
 * label is a block element in the flow: a full-width bar of the peer's colour
 * across the page under the line they are on, which is what it looked like
 * the first time.
 *
 * `:deep`, because the prose is inside `<EditorContent>` and these elements
 * are decorations ProseMirror creates rather than anything this template
 * writes.
 */
:deep(.collaboration-carets__caret) {
  position: relative;
  /* A caret occupies no width. `border-left` with negative margins puts a
     line *between* two characters rather than pushing them apart, which is
     the difference between a cursor and a character. */
  margin-left: -1px;
  margin-right: -1px;
  border-left: 2px solid;
  border-right: 2px solid;
  border-color: inherit;
  pointer-events: none;
  word-break: normal;
}

:deep(.collaboration-carets__label) {
  position: absolute;
  top: -1.35em;
  left: -2px;
  padding: 0.05rem 0.3rem;
  border-radius: 0.25rem 0.25rem 0.25rem 0;
  font-size: 0.6875rem;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  color: #fff;
  user-select: none;
  /* Out of the way until it is wanted. A name over every caret is fine with
     one other person and is a row of flags over the prose with four; the bar
     is what says somebody is there, and the strip in the header says who.
     Hovering the line brings the names back. */
  opacity: 0;
  transition: opacity 120ms ease;
}

:deep(.ProseMirror:hover .collaboration-carets__label),
:deep(.collaboration-carets__caret:hover .collaboration-carets__label) {
  opacity: 1;
}

/* What they have selected, behind the text rather than over it. */
:deep(.collaboration-carets__selection) {
  mix-blend-mode: multiply;
  opacity: 0.25;
  pointer-events: none;
}

/*
 * The sheet.
 *
 * White paper on a grey desk, and nothing else — where the pages end is
 * measured and drawn by `paginate()`, not painted on with a repeating
 * gradient. A gradient could only ever say "a page is this tall"; the gaps say
 * "this page ends here", which is a different and truer claim.
 */
.doc-sheet {
  background-color: #ffffff;
}
</style>

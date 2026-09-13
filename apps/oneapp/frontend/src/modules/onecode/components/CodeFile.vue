<template>
  <!--
    One source file, open. OneCode.

    The same `File` and the same bytes as before — this is not a new store, it
    is the editor `PlainText` used to be, given the chrome the thing deserves.
    What somebody downloads has to be the file they wrote, so what they edit is
    its bytes: the same key, replaced in place. A markdown file round-tripped
    through ProseMirror would come back reflowed, re-escaped and no longer the
    thing anybody committed, which is why the rich editor is not an option here
    even for the one language that could survive it.

    The shared `EditorChrome` above it, so this is the same bar as the document
    and the workbook — one trail, one title typed in place, one mark. `hosted`
    is what keeps it working unchanged inside the Drive's pane, where a
    teleported header would land above the file list instead.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <!--
      The same bar as the document and the workbook — §E2/E3, §E9's fifth
      rail. It drew its own for a stage: a mark that was also the way out, a
      title input, a save state and four buttons, all of it a hand-made copy
      of what `EditorChrome` already carried. The copy was the thing §E9 says
      must not happen — *a second editor* — arriving as a bar rather than as
      an editor, which is how it went unnoticed.
    -->
    <EditorChrome
      brand="onecode"
      :crumbs="crumbs"
      :title="title"
      :placeholder="__('Untitled file')"
      :renamable="!!doc.can_write"
      :hosted="hosted"
      @update:title="renameTo"
    >
      <template #status>
        <!-- What it is, and whether that means anything to CodeMirror. The
             tooltip is the honest half: a language with no pack still opens,
             still numbers its lines and still saves — it is not coloured, and
             a person looking at grey Rust deserves to know which of the two
             it is. -->
        <Tooltip v-if="languageLabel" :text="highlighted
          ? __('{0}, highlighted', [languageLabel])
          : __('{0}. This one has no syntax pack, so it opens uncoloured.', [languageLabel])">
          <Badge
            theme="gray"
            variant="subtle"
            size="sm"
            data-slot="code-language"
            :label="languageLabel"
          />
        </Tooltip>
        <span class="shrink-0 text-p-xs text-ink-muted">{{ state }}</span>
      </template>

      <template #actions>
        <!-- The other files in the folder, when there are any. A project is a
             folder and nothing else — §E9's first rail — so this is the whole
             of what makes one editable as a project: the tree is the folder's
             own rows, and moving between them is a route change. -->
        <Button
          v-if="doc.folder"
          variant="ghost"
          size="sm"
          icon="lucide-folder-tree"
          data-slot="code-tree"
          :label="__('Files in this folder')"
          :tooltip="__('Files in this folder')"
          :class="showTree ? 'bg-surface-gray-2' : ''"
          @click="showTree = !showTree"
        />

        <!-- Markdown, read. Not a second editor and not a mode: the source is
             still the file, and this is a look at what it renders to. Only for
             the one language where the rendered form is the point — a preview
             of Python would be Python. -->
        <Button
          v-if="canRead"
          variant="ghost"
          size="sm"
          :icon-left="reading ? 'lucide-pencil' : 'lucide-book-open'"
          data-slot="code-read"
          :label="reading ? __('Edit') : __('Read')"
          :tooltip="reading ? __('Back to the source') : __('Read it as it renders')"
          @click="reading = !reading"
        />

        <Button
          variant="ghost"
          size="sm"
          icon="lucide-history"
          data-slot="code-history"
          :label="__('Version history')"
          :tooltip="__('Version history')"
          :class="showHistory ? 'bg-surface-gray-2' : ''"
          @click="showHistory = !showHistory"
        />

        <Button
          variant="ghost"
          size="sm"
          icon="lucide-download"
          :label="__('Download')"
          :tooltip="__('Download')"
          @click="download"
        />
      </template>
    </EditorChrome>

    <!--
      The editor owns the height and the scrolling, which is why there is no
      `FadedScroll` here and no wrapper that scrolls. CodeMirror keeps its
      gutter pinned while its content moves under it, and a second scroller
      around that is how you get a line-number column that scrolls away from
      the lines it numbers.
    -->
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <!-- What is on screen is not what the file says. Said plainly, because
             an editor showing something other than the file, with no sign of
             it, is how somebody types into the past. -->
        <div
          v-if="looking"
          class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-amber-2 bg-surface-amber-1 px-3 py-1.5"
          data-slot="code-looking"
        >
          <span class="truncate text-sm text-ink-amber-3">
            {{ __('Looking at {0}. Nothing here is being saved.', [looking.title]) }}
          </span>
          <Button
            variant="ghost"
            size="sm"
            :label="__('Back to now')"
            @click="stopLooking"
          />
        </div>
      <div v-if="reading" class="min-h-0 flex-1 overflow-auto px-8 py-6">
        <CodePreview :model-value="text" language="markdown" data-slot="code-preview" />
      </div>
      <!-- `fills` on the wrapper rather than on `CodeEditor`: scoped CSS reaches
           a child's root, but `:deep()` under a class is a descendant selector
           and CodeEditor's root *is* the `.cm-editor`. -->
      <div v-else class="fills min-h-0 flex-1">
        <CodeEditor
          v-model="text"
          :language="highlight || 'plain'"
          :disabled="!doc.can_write"
          variant="subtle"
          size="md"
          data-slot="code-body"
          :aria-label="__('File contents')"
          @update:model-value="onChange"
        />
      </div>
      </div>

      <!-- The folder this file is in, when it holds others this opens. §E9's
           first rail: a project *is* the folder, so the tree is its listing. -->
      <CodeTree
        v-if="showTree && doc.folder"
        :folder="doc.folder"
        :current="name"
        :title="title"
        @close="showTree = false"
      />

      <!--
        The same panel a document and a sheet get, over the same rows. A version
        of a `.py` is a blob and a moment like any other — see
        `shared/versions.py`, where `Text` is the third store rather than a
        second mechanism.
      -->
      <VersionPanel
        v-if="showHistory"
        :file="name"
        kind="Text"
        :can-write="doc.can_write"
        :revision="revision"
        @close="showHistory = false"
        @preview="preview"
        @restored="restored"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Badge, Button, CodeEditor, CodePreview, Tooltip } from '@/ui'
import CodeTree from '@/modules/onecode/components/CodeTree.vue'
import EditorChrome from '@/shared/components/EditorChrome.vue'
import VersionPanel from '@/modules/onespace/components/versions/VersionPanel.vue'
import { downloadUrl } from '@/modules/onestorage/lib/files'
import { highlightFor, labelForLanguage } from '@/modules/onestorage/lib/languages'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import { __ } from '@/shared/lib/runtime/translate'
import { workspace } from '@/shared/lib/workspace'
import { ago } from '@/shared/lib/runtime/format'

const props = defineProps({
  name: { type: String, required: true },
  doc: { type: Object, required: true },
  /** Inside the Drive's pane rather than on a page — `EditorChrome.hosted`. */
  hosted: { type: Boolean, default: false },
})

const emit = defineEmits(['renamed'])

const QUIET_MS = 1200

const title = ref(props.doc.title || '')
const text = ref(props.doc.content || '')
const reading = ref(false)
const showHistory = ref(false)
const showTree = ref(false)

// The same root every editor opens with — §C1. A file in a folder gets that
// folder's crumb after it, which is also the only place a project's name
// appears: there is no project object to take a name from.
const crumbs = useCrumbs(
  { label: __('Files'), route: { name: 'Drive' } },
  () => (props.doc.folder
    ? [{ label: __('This folder'), route: { name: 'Drive', query: { folder: props.doc.folder } } }]
    : []),
)

/** Renamed in the bar, saved the way every other keystroke is. */
async function renameTo(next) {
  title.value = next
  await save()
}

//: Bumped after every save, so the history panel follows the work rather than
//: needing a refresh button beside it. The same contract the document editor
//: has with the same component.
const revision = ref(0)
const busy = ref(false)
const dirty = ref(false)
const failed = ref('')
const savedAt = ref(props.doc.modified || '')

let timer = null

// The extension, and everything derived from it. Read from the *edited* title
// rather than from what the server said, so renaming `notes.txt` to `notes.md`
// colours it and offers the reader before the save lands.
const extension = computed(() => {
  const name = title.value || props.doc.title || ''
  return name.includes('.') ? name.split('.').pop().toLowerCase() : ''
})

const highlight = computed(() => highlightFor(extension.value))
const highlighted = computed(() => !!highlight.value)
const languageLabel = computed(() => (extension.value ? labelForLanguage(extension.value) : ''))
const canRead = computed(() => highlight.value === 'markdown')

const state = computed(() => {
  if (failed.value) return failed.value
  if (busy.value) return __('Saving…')
  if (dirty.value) return __('Unsaved')
  if (!savedAt.value) return ''
  return __('Saved {0}', [ago(savedAt.value)])
})

function onChange() {
  if (!props.doc.can_write || looking.value) return
  dirty.value = true
  failed.value = ''
  clearTimeout(timer)
  timer = setTimeout(() => save(), QUIET_MS)
}

async function save() {
  if (!props.doc.can_write || busy.value) return
  clearTimeout(timer)
  busy.value = true
  try {
    await workspace.textSave(props.name, { content: text.value, title: title.value })
    dirty.value = false
    savedAt.value = new Date().toISOString()
    revision.value += 1
    emit('renamed', title.value)
  } catch (raised) {
    failed.value = raised?.messages?.[0] || __('Could not save')
  } finally {
    busy.value = false
  }
}

// The way out is the trail, on a page, and the pane's own Close inside it —
// both `EditorChrome`'s and `FilePane`'s, neither this component's. It drew a
// Close button of its own, which is why `hosted` had to be threaded through
// two components to stop it routing away from the list it was sitting beside.
// `onBeforeUnmount` still flushes an unsaved second, whichever way out was
// taken.

const download = () => { window.location.href = downloadUrl(props.name) }

/**
 * Looking at an old version, without leaving.
 *
 * The panel hands over the version *row*; the body is a second call, because a
 * history of forty versions is forty blobs nobody asked to download. The editor
 * shows it read-only until Restore — `looking` is what says so, and it is also
 * what stops the autosave from writing an old body back over the current one
 * two seconds after somebody glances at it.
 */
const looking = ref(null)

async function preview(one) {
  const answer = await workspace.fileVersionBody(one.name, 'Text')
  looking.value = one
  text.value = answer?.payload ?? text.value
}

/** Restore wrote it server-side; this is the editor catching up. */
async function restored() {
  const answer = await workspace.textOpen(props.name)
  looking.value = null
  text.value = answer?.content || ''
  dirty.value = false
  savedAt.value = new Date().toISOString()
  revision.value += 1
}

/** Back to what the file actually says, after looking at an old version. */
async function stopLooking() {
  const answer = await workspace.textOpen(props.name)
  looking.value = null
  text.value = answer?.content || ''
}

watch(() => props.doc, (next) => {
  title.value = next.title || ''
  text.value = next.content || ''
  reading.value = false
  dirty.value = false
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  if (dirty.value) save()
})
</script>

<style scoped>
/*
 * The editor fills the room it is given.
 *
 * CodeMirror sizes itself to its content and caps at `--cm-max-height`, which
 * is right for a field in a form and wrong for a file: a twelve-line script
 * would otherwise draw a twelve-line box with the page white underneath it,
 * and clicking that white would not put the caret anywhere. So the cap comes
 * off and the height becomes the pane's.
 */
/*
 * Two elements, not one. frappe-ui's `CodeEditor` draws a `.code-editor`
 * wrapper around the `.cm-editor`, and only the inner one was given a height —
 * so the rule below was true and the box was still 74px tall, because its
 * parent was. A `RATE = 0.05` in a two-line box with six hundred pixels of
 * page under it, and clicking that page put the caret nowhere.
 */
.fills :deep(.code-editor),
.fills :deep(.cm-editor) {
  height: 100%;
  max-height: none;
}

.fills :deep(.cm-scroller) {
  overflow: auto;
}
</style>

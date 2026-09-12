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

    Its own bar rather than the shell's teleported header, which is the choice
    the sheet editor makes and for the same reason: an editor is a room you are
    in, and a breadcrumb above it belongs to the page you came from. It also
    means the whole thing works unchanged inside the Drive's pane.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <div
      class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-2 bg-surface-base px-3"
    >
      <!-- The mark and the way out are one control, as in the sheet: at rest
           it says what this is, under the pointer it says where it goes.

           not-a-tooltip: the `group-hover` here cross-fades the mark to an
           arrow inside one button. It reveals no content and carries no text —
           the hover text on it is a real frappe-ui `Tooltip`, two lines down. -->
      <button
        type="button"
        class="group flex shrink-0 items-center gap-1.5 rounded-4 py-0.5 pe-2 ps-0.5 hover:bg-surface-gray-2"
        data-slot="code-brand"
        :aria-label="__('Back to Files')"
        @click="leave"
      >
        <Tooltip :text="__('Back to Files')">
          <span class="relative block size-7 shrink-0">
            <BrandMark
              name="onecode"
              class="absolute inset-0 transition-opacity group-hover:opacity-0"
            />
            <Icon
              name="lucide-arrow-left"
              class="absolute inset-0 size-7 p-0.5 text-ink-secondary opacity-0 transition-opacity group-hover:opacity-100"
            />
          </span>
        </Tooltip>
        <!-- And the name beside it. The mark alone is recognisable to somebody
             who already knows it and says nothing to somebody who does not,
             which is everybody on their first day. Hidden on a phone, where the
             filename is the only thing there is room for. -->
        <SpaceName brand="onecode" class="hidden text-base font-medium md:block" />
      </button>

      <!-- The name, edited where it is shown. A `.py` renamed to `.sql` is a
           `.sql` on the next open, because the language is the extension and
           nothing else — there is no second field that could disagree. -->
      <input
        v-model="title"
        name="file-title"
        data-slot="code-title"
        spellcheck="false"
        :disabled="!doc.can_write"
        class="min-w-0 flex-1 truncate rounded-4 border-none bg-transparent px-2 py-1 text-base font-medium text-ink-primary outline-none hover:bg-surface-gray-2 focus:bg-surface-gray-2"
        :aria-label="__('File name')"
        @change="save"
      />

      <span class="shrink-0 text-p-xs text-ink-muted">{{ state }}</span>

      <!-- What it is, and whether that means anything to CodeMirror. The
           tooltip is the honest half: a language with no pack still opens,
           still numbers its lines and still saves — it is not coloured, and a
           person looking at grey Rust deserves to know which of the two it is. -->
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

      <!-- Markdown, read. Not a second editor and not a mode: the source is
           still the file, and this is a look at what it renders to. Only for
           the one language where the rendered form is the point — a preview of
           Python would be Python. -->
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
    </div>

    <!--
      The editor owns the height and the scrolling, which is why there is no
      `FadedScroll` here and no wrapper that scrolls. CodeMirror keeps its
      gutter pinned while its content moves under it, and a second scroller
      around that is how you get a line-number column that scrolls away from
      the lines it numbers.
    -->
    <div class="flex min-h-0 flex-1 overflow-hidden">
      <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
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
      <div v-if="reading" class="h-full overflow-auto px-8 py-6">
        <CodePreview :model-value="text" language="markdown" data-slot="code-preview" />
      </div>
      <!-- `fills` on the wrapper rather than on `CodeEditor`: scoped CSS reaches
           a child's root, but `:deep()` under a class is a descendant selector
           and CodeEditor's root *is* the `.cm-editor`. -->
      <div v-else class="fills h-full">
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

import { Badge, Button, CodeEditor, CodePreview, Icon, Tooltip, dayjsLocal } from '@/ui'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import VersionPanel from '@/modules/onespace/components/versions/VersionPanel.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { downloadUrl } from '@/modules/onestorage/lib/files'
import { highlightFor, labelForLanguage } from '@/modules/onestorage/lib/languages'
import { __ } from '@/shared/lib/runtime/translate'
import { workspace } from '@/shared/lib/workspace'

const props = defineProps({
  name: { type: String, required: true },
  doc: { type: Object, required: true },
})

const emit = defineEmits(['renamed', 'close'])

const QUIET_MS = 1200

const title = ref(props.doc.title || '')
const text = ref(props.doc.content || '')
const reading = ref(false)
const showHistory = ref(false)

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
  return __('Saved {0}', [dayjsLocal(savedAt.value).fromNow()])
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

/**
 * Out, with whatever was typed in the last second saved first.
 *
 * Only ever an emit. Where "out" goes is the host's to answer and the two hosts
 * answer differently: on a page it is a route, in the Drive's pane it is
 * closing the pane — and a route change there would take the list away with it,
 * which is the one thing the pane exists to avoid.
 */
async function leave() {
  if (dirty.value) await save()
  emit('close')
}

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
.fills :deep(.cm-editor) {
  height: 100%;
  max-height: none;
}

.fills :deep(.cm-scroller) {
  overflow: auto;
}
</style>

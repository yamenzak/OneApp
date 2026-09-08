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
    <!-- The shell's header, teleported, rather than a second bar of our own:
         the document is a file, so it opens with the same trail every other
         page does — Files, then what it is called. Renaming goes through the
         menu, the way it does in the Drive, so there is one rename in the
         product rather than an editable title here and a dialog there. -->
    <PageHeader>
      <nav data-slot="breadcrumb" :aria-label="__('Breadcrumb')" class="flex min-w-0 items-center gap-2">
        <!-- The mark and the name, ahead of the trail. Not a control: the
             first crumb is already Files, and a logo that navigates where the
             word beside it navigates is one of them too many. It is here
             because the corner of a document is where a product says what it
             is, and a breadcrumb on its own said nothing.

             The name as well as the mark, because a mark alone is recognisable
             to somebody who already knows it and says nothing to somebody who
             does not — which is everybody on their first day. Hidden on a
             phone, where the trail is the only thing there is room for. -->
        <BrandMark name="onedoc" class="size-6 shrink-0" />
        <SpaceName brand="onedoc" class="hidden shrink-0 text-base font-medium sm:block" />
        <span class="hidden shrink-0 text-ink-gray-3 sm:block" aria-hidden="true">·</span>
        <Breadcrumbs :items="crumbs" />
      </nav>

      <div class="flex shrink-0 items-center gap-2">
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

        <span class="text-p-xs text-ink-gray-5">{{ state }}</span>
        <Button
          variant="ghost"
          icon="lucide-history"
          :label="__('Version history')"
          :tooltip="__('Version history')"
          :class="showHistory ? 'bg-surface-gray-2' : ''"
          @click="showHistory = !showHistory"
        />
        <Dropdown :options="menu">
          <Button
            variant="ghost"
            icon="lucide-more-horizontal"
            :label="__('What to do with this document')"
            :tooltip="__('What to do with this document')"
          />
        </Dropdown>
      </div>
    </PageHeader>

    <div class="flex min-h-0 flex-1">
      <Outline :editor="editor" :revision="revision" />

      <div class="flex min-w-0 flex-1 flex-col">
        <Editor
          v-model="content"
          :extensions="EXTENSIONS"
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
              :items="documentToolbar"
              class="shrink-0 overflow-x-auto border-b border-outline-gray-1 px-4 py-1.5"
            />
            <EditorTableMenu v-if="doc.can_write" :editor="instance" />

            <!-- Paged, the scroller is a desk and the document is a sheet on
                 it. Pageless, it is what it always was: prose in the middle of
                 the window with nothing behind it. -->
            <FadedScroll class="min-h-0 flex-1" :class="paper.paged ? 'bg-surface-gray-2' : ''">
              <div
                class="mx-auto"
                :class="paper.paged
                  ? ['doc-sheet my-8 shadow-sm', ...bodyClasses(settings)]
                  : ['w-full px-6 py-10', ...pageClasses(settings)]"
                :style="paperStyle(settings)"
              >
                <!--
                  The letter head, where it will be when this is printed.

                  Once, at the top, rather than at the top of every page: real
                  pagination is what the print engine does, and drawing a
                  repeat here would mean guessing where the page breaks fall
                  and putting the guess on top of somebody's paragraph. The
                  guide lines say where the pages are; this says what is at the
                  top of each of them. Subtle for the same reason — it is not
                  content and it is not editable, and it should not read as
                  either.

                  `v-html` because `Letter Head.validate` scrubs the markup on
                  the way in, which is the same reason the settings screen
                  renders its preview this way.
                -->
                <div
                  v-if="paper.paged && headMarkup"
                  class="pointer-events-none mb-6 select-none border-b border-outline-gray-2 pb-3 opacity-60"
                  aria-hidden="true"
                  v-html="headMarkup"
                />
                <EditorContent
                  :editor="instance"
                  :aria-label="__('Document')"
                  dir="auto"
                  class="prose prose-sm max-w-none"
                />
              </div>
            </FadedScroll>
          </template>
        </Editor>

        <footer
          class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-gray-1 px-4 py-1.5 text-p-xs text-ink-gray-5"
        >
          <span>{{ counted }}</span>
          <span v-if="settings.locked" class="flex items-center gap-1">
            <Icon name="lucide-lock" class="size-3" />
            {{ __('Locked — unlock it from the menu to type') }}
          </span>
        </footer>
      </div>

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

    <DocSettings v-model="showSettings" v-model:settings="settings" @change="save()" />

    <TemplatePicker
      v-model="picking"
      :rows="templates"
      icon="lucide-file-signature"
      :said="__('This opens the template as a new document. What you have here is not touched.')"
      @pick="fromTemplate"
    />

    <!-- The Drive's rename, in the Drive's shape: one dialog, one field, one
         button. A document renamed here is renamed there, because they are the
         same `File`. -->
    <Dialog v-model="renaming" :title="__('Rename')">
      <template #default>
        <FormControl v-model="draftTitle" :label="__('Name')" @keyup.enter="rename" />
      </template>
      <template #actions>
        <Button variant="solid" :label="__('Rename')" :loading="busy" @click="rename" />
      </template>
    </Dialog>

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
          :extensions="EXTENSIONS"
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
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  Button,
  Dialog,
  Breadcrumbs,
  Dropdown,
  Editor,
  EditorContent,
  EditorFixedMenu,
  EditorTableMenu,
  FormControl,
  Icon,
  PageHeader,
  RichTextKit,
  Skeleton,
  dayjsLocal,
} from '@/ui'
import FadedScroll from '../FadedScroll.vue'
import DocSettings from './DocSettings.vue'
import Outline from './Outline.vue'
import VersionPanel from '../versions/VersionPanel.vue'
import TemplatePicker from '../drive/TemplatePicker.vue'
import BrandMark from '../brand/BrandMark.vue'
import SpaceName from '../brand/SpaceName.vue'
import { bodyClasses, documentToolbar, pageClasses } from './toolbar'
import { paperSetup, paperStyle } from '@/lib/paper/setup'
import { printHtml } from '@/lib/paper/print'
import { useOutline } from '@/composables/useOutline'
import { putFile } from '@/lib/files/attach'
import { workspace } from '@/lib/workspace'
import { cameFrom } from '@/lib/screen/returnTo'
import { __ } from '@/lib/runtime/translate'

const route = useRoute()

const props = defineProps({
  name: { type: String, required: true },
  doc: { type: Object, required: true },
})

const emit = defineEmits(['renamed', 'reload'])

// The whole capability of the editor. RichTextKit is frappe-ui's article-grade
// bundle, which is the right one for a document — the lighter CommentKit is
// built for a box inside a form.
const EXTENSIONS = [RichTextKit]

//: How long after the last keystroke a save goes out. Long enough that typing
//: a sentence is one save; short enough that closing the tab mid-thought loses
//: at most this.
const QUIET_MS = 1200

const title = ref(props.doc.title || '')
const content = ref(props.doc.content ? JSON.parse(props.doc.content) : null)
const settings = ref({ ...(props.doc.settings || {}) })

const editor = ref(null)
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
 * `paper` is the same resolution `oneapp_core/paper.py` does on the way out,
 * so what the sheet on screen is is what the printer gets. `headMarkup` is the
 * chosen letter head's HTML, fetched once when a document that has one opens —
 * a document with no letter head, which is most of them, asks for nothing.
 */
const paper = computed(() => paperSetup(settings.value))
const headMarkup = ref('')

watch(
  () => [paper.value.paged, paper.value.letterHead],
  async ([paged, head]) => {
    if (!paged || !head) return (headMarkup.value = '')
    try {
      headMarkup.value = (await workspace.letterHead(head))?.content || ''
    } catch {
      // A letter head somebody deleted is a document that prints without one,
      // which is what `paper.letter_head_html` decides on the server too.
      headMarkup.value = ''
    }
  },
  { immediate: true },
)

const showHistory = ref(false)
const renaming = ref(false)
const draftTitle = ref('')
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
    icon: one.level > 2 ? 'minus' : 'hash',
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
  return __('Saved {0}', [dayjsLocal(savedAt.value).fromNow()])
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

// The trail says where this document sits. Usually that is the Drive; when it
// was opened from a record it is that record, so the crumb is a way back to
// what you were reading rather than a way to a folder you never visited —
// `lib/screen/returnTo.js`.
const back = computed(() => cameFrom(route))

const crumbs = computed(() => [
  back.value
    ? { label: back.value.label, route: back.value.path }
    : { label: __('Files'), route: { name: 'Drive' } },
  { label: title.value || __('Untitled document') },
])

async function rename() {
  title.value = draftTitle.value
  renaming.value = false
  await save()
}

const isTemplate = ref(!!props.doc.is_template)

const menu = computed(() => [
  {
    // Where a template is reached from, now that it is not in the New menu.
    // A blank page is when you realise you wanted one, and a new document is
    // what it opens — this one is left exactly as it was, which is the whole
    // reason it is not called "apply".
    label: __('Load a template'),
    icon: 'bookmark',
    onClick: () => { picking.value = true },
  },
  {
    label: __('Rename'),
    icon: 'pencil',
    condition: () => props.doc.can_write,
    onClick: () => { draftTitle.value = title.value; renaming.value = true },
  },
  { label: __('Page setup'), icon: 'settings-2', onClick: () => { showSettings.value = true } },
  {
    label: settings.value.locked ? __('Unlock') : __('Lock against typing'),
    icon: settings.value.locked ? 'unlock' : 'lock',
    condition: () => props.doc.can_write,
    onClick: () => {
      settings.value = { ...settings.value, locked: !settings.value.locked }
      save()
    },
  },
  {
    // The page the server builds, printed from a frame of its own — the size,
    // the margins and the letter head on every sheet are all in that page and
    // none of them are in this window. `lib/paper/print.js`.
    label: __('Print'),
    icon: 'printer',
    onClick: async () => {
      if (dirty.value) await save()
      const found = await workspace.docPrintable(props.name)
      if (found?.html) await printHtml(found.html)
    },
  },
  {
    label: __('Download as HTML'),
    icon: 'download',
    onClick: () => {
      window.location.href =
        `/api/method/oneapp.oneapp_core.docs.download?name=${encodeURIComponent(props.name)}`
    },
  },
  {
    label: __('Copy as Markdown'),
    icon: 'clipboard',
    onClick: async () => {
      const answer = await workspace.docMarkdown(props.name)
      await navigator.clipboard.writeText(answer?.markdown || '')
    },
  },
  {
    label: __('Duplicate'),
    icon: 'copy',
    onClick: () => workspace.docDuplicate(props.name, __('{0} copy', [title.value])),
  },
  {
    // A template is a document with a flag on it, so this is the whole feature
    // — see `oneapp_core/docs/templates.py`. It then appears in the New menu,
    // in the Drive and on a record's Files tab alike.
    label: isTemplate.value ? __('Stop using as a template') : __('Use as a template'),
    icon: isTemplate.value ? 'bookmark-minus' : 'bookmark-plus',
    condition: () => props.doc.can_write,
    onClick: async () => {
      const next = !isTemplate.value
      await workspace.docSetTemplate(props.name, next)
      isTemplate.value = next
    },
  },
])

// A save the moment the page goes away, because the quiet timer has not fired
// yet and the last sentence is the one worth keeping.
watch(() => props.doc, (next) => {
  title.value = next.title || ''
  isTemplate.value = !!next.is_template
  content.value = next.content ? JSON.parse(next.content) : null
  settings.value = { ...(next.settings || {}) }
  dirty.value = false
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  if (dirty.value) save()
})
</script>

<style scoped>
/*
 * The sheet, and where its pages end.
 *
 * One repeating gradient rather than an element per page: the editor has no
 * idea how many pages there are — the browser works that out when it
 * paginates, and it only paginates when it prints. What it can say truthfully
 * is that a page is this tall, so a hairline every page-height is a guide
 * rather than a claim. `--page-height` comes from `paperStyle`.
 *
 * `background-origin: border-box` because the sheet's padding is the page
 * margin: measured from the padding box the first guide would land a margin
 * too low, and every one after it would drift.
 */
.doc-sheet {
  /* At least one page. A paged document shorter than its page is still a
     page — a sheet that stops where the words stop is the pageless layout
     with a border round it. */
  min-height: var(--page-height);
  background-color: #ffffff;
  background-image: linear-gradient(
    to bottom,
    transparent calc(100% - 1px),
    rgb(0 0 0 / 8%) calc(100% - 1px)
  );
  background-size: 100% var(--page-height);
  background-repeat: repeat-y;
  background-origin: border-box;
  background-clip: border-box;
}
</style>

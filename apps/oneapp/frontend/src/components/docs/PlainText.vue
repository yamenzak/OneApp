<template>
  <!--
    A `.txt`, `.md` or `.csv`, edited as itself.

    Not the rich editor. What somebody downloads has to be the file they wrote,
    so what they edit is its bytes — the same key, replaced in place. A
    markdown file that round-tripped through ProseMirror would come back
    reflowed, re-escaped and no longer the thing anybody committed.

    `CodeEditor` rather than a textarea because it is already in the barrel,
    it numbers the lines, and Markdown is one of the languages it knows.
  -->
  <div class="flex h-full min-h-0 flex-col">
    <PageHeader>
      <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center gap-1">
        <Breadcrumbs :items="crumbs" />
      </nav>

      <div class="flex shrink-0 items-center gap-2">
        <span class="text-p-xs text-ink-gray-5">{{ state }}</span>
        <Button
          icon-left="lucide-download"
          label="Download"
          variant="ghost"
          tooltip="Download"
          @click="download"
        />
      </div>
    </PageHeader>

    <FadedScroll class="min-h-0 flex-1">
      <CodeEditor
        v-model="text"
        :language="language"
        :disabled="!doc.can_write"
        class="min-h-full"
        @update:model-value="onChange"
      />
    </FadedScroll>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { Breadcrumbs, Button, CodeEditor, PageHeader, dayjsLocal } from '@/ui'
import { cameFrom } from '@/lib/screen/returnTo'
import FadedScroll from '../FadedScroll.vue'
import { workspace } from '@/lib/workspace'

const route = useRoute()

const props = defineProps({
  name: { type: String, required: true },
  doc: { type: Object, required: true },
})

const emit = defineEmits(['renamed'])

const QUIET_MS = 1200

//: What CodeMirror should call this. `md` is the one worth mapping — the rest
//: are their own extension, and one it does not know is plain text.
const LANGUAGES = { md: 'markdown', markdown: 'markdown', yml: 'yaml' }

const title = ref(props.doc.title || '')
const text = ref(props.doc.content || '')
const busy = ref(false)
const dirty = ref(false)
const failed = ref('')
const savedAt = ref(props.doc.modified || '')

let timer = null

// The record it was opened from, when it was — same rule the document editor
// follows, in `lib/screen/returnTo.js`.
const back = computed(() => cameFrom(route))

const crumbs = computed(() => [
  back.value
    ? { label: back.value.label, route: back.value.path }
    : { label: 'Files', route: { name: 'Drive' } },
  { label: title.value || 'Untitled' },
])

const language = computed(() => LANGUAGES[props.doc.language] || props.doc.language || 'text')

const state = computed(() => {
  if (failed.value) return failed.value
  if (busy.value) return 'Saving…'
  if (dirty.value) return 'Unsaved'
  if (!savedAt.value) return ''
  return `Saved ${dayjsLocal(savedAt.value).fromNow()}`
})

function onChange() {
  if (!props.doc.can_write) return
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
    emit('renamed', title.value)
  } catch (raised) {
    failed.value = raised?.messages?.[0] || 'Could not save'
  } finally {
    busy.value = false
  }
}

const download = () => {
  window.location.href =
    `/api/method/oneapp.oneapp_core.storage.r2.download?file=${encodeURIComponent(props.name)}`
}

watch(() => props.doc, (next) => {
  title.value = next.title || ''
  text.value = next.content || ''
  dirty.value = false
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  if (dirty.value) save()
})
</script>

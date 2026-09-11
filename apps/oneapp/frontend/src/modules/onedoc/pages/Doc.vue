<template>
  <!--
    One document, or one text file, open.

    A page rather than a screen inside a Space, for the same reason Sheets,
    Mail and Files are: a document belongs to the workspace's file table, not
    to any one Space. It is reached from the Drive, from an attachment on a
    record, or from a link somebody sent — and none of those knows which Space
    you were in.

    Two editors behind one address, because there is one thing here: a `File`.
    Which editor opens is what the file *is* — prose in a `Doc Body` row, or
    bytes in R2 — and that is the server's answer, not a route parameter. A
    `.py`, a `.md` and a `.txt` are all the second one: OneCode is the editor
    for anything whose content is its own bytes, coloured where CodeMirror has
    a pack for it and plain where it does not.
  -->
  <div v-if="failed" class="p-8">
    <EmptyState
      icon="lucide-file-question"
      :title="__('That document did not open')"
      :description="failed"
    />
  </div>

  <div v-else-if="!doc" class="flex h-full flex-col gap-3 p-8">
    <Skeleton class="h-8 w-64" />
    <Skeleton class="h-4 w-full" />
    <Skeleton class="h-4 w-5/6" />
    <Skeleton class="h-4 w-2/3" />
  </div>

  <CodeFile
    v-else-if="doc.language"
    :name="name"
    :doc="doc"
    @renamed="onRenamed"
    @close="leave"
  />

  <!--
    Keyed by the document, so walking from one to another builds a new editor
    rather than re-pointing this one. It used to be reused, and that was fine
    while an editor was a box with text in it. It is not fine now: the editor
    is bound to a Y.Doc that belongs to one file and to a room joined for that
    file, and re-pointing it would leave both behind — the second document
    would be typed into the first one's room.
  -->
  <DocEditor v-else :key="name" :name="name" :doc="doc" @renamed="onRenamed" @reload="load" />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Skeleton } from '@/ui'
import DocEditor from '@/modules/onedoc/components/DocEditor.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import CodeFile from '@/modules/onecode/components/CodeFile.vue'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'
import { cameFrom } from '@/modules/onespace/lib/screen/returnTo'
import { workspace } from '@/shared/lib/workspace'

const props = defineProps({
  name: { type: String, required: true },
  /**
   * Whether something else is holding this — the Drive's pane, today.
   *
   * It changes one thing: where "out" goes. On a page it is a route, and in a
   * pane a route would take the list away with it, which is the one thing the
   * pane exists to avoid. `CodeFile.leave` says exactly this and emits rather
   * than navigating; this is the half that was missing, so its Close button
   * navigated anyway.
   */
  hosted: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const route = useRoute()
const router = useRouter()

// Where "out" goes, which the editor asks and does not answer: the record it
// was opened from when there was one, and the Drive otherwise.
const back = computed(() => cameFrom(route))
const leave = () =>
  props.hosted ? emit('close') : router.push(back.value ? back.value.path : { name: 'Drive' })

const doc = ref(null)
const failed = ref('')

async function load() {
  doc.value = null
  failed.value = ''
  try {
    // The document first, because that is what this address usually is. A
    // `.md` answers "that file is not a document", and the text call is the
    // second question rather than a third route.
    doc.value = await workspace.docOpen(props.name)
  } catch {
    try {
      doc.value = await workspace.textOpen(props.name)
    } catch (raised) {
      failed.value = errorText(raised)
    }
  }
}

// The tab, so a person with four documents open can tell them apart.
const onRenamed = (title) => {
  if (title) document.title = title
}

watch(() => props.name, load, { immediate: true })
</script>

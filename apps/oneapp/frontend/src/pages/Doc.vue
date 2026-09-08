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

  <DocEditor v-else :name="name" :doc="doc" @renamed="onRenamed" @reload="load" />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Skeleton } from '@/ui'
import DocEditor from '../components/docs/DocEditor.vue'
import EmptyState from '../components/EmptyState.vue'
import CodeFile from '../components/code/CodeFile.vue'
import { errorText } from '@/lib/runtime/errors'
import { __ } from '@/lib/runtime/translate'
import { cameFrom } from '@/lib/screen/returnTo'
import { workspace } from '@/lib/workspace'

const props = defineProps({
  name: { type: String, required: true },
})

const route = useRoute()
const router = useRouter()

// Where "out" goes, which the editor asks and does not answer: the record it
// was opened from when there was one, and the Drive otherwise.
const back = computed(() => cameFrom(route))
const leave = () => router.push(back.value ? back.value.path : { name: 'Drive' })

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

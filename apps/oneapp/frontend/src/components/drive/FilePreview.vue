<!--
  Looking at a file without downloading it.

  Six kinds and a fallback, which is the set that covers a workspace's files.
  Everything points at the same URL — `r2.download`, which checks the reader's
  permission and then redirects to a presigned object. A `<video>` following a
  302 is a `<video>` that plays, so streaming needs nothing of ours.
-->
<template>
  <Dialog v-model="open" :title="file?.file_name || 'File'" size="4xl">
    <template #default>
      <div class="grid min-h-[24rem] place-items-center">
        <img
          v-if="kind === 'Image'"
          :src="url"
          :alt="file.file_name"
          class="max-h-[70vh] w-auto rounded-6 object-contain"
        />

        <!-- A PDF is the browser's own viewer. Rendering one ourselves would
             be shipping a PDF engine to save an iframe. -->
        <iframe
          v-else-if="kind === 'PDF'"
          :src="url"
          :title="file.file_name"
          class="h-[70vh] w-full rounded-6 border border-outline-gray-1"
        />

        <video v-else-if="kind === 'Video'" :src="url" controls class="max-h-[70vh] w-full rounded-6" />

        <audio v-else-if="kind === 'Audio'" :src="url" controls class="w-full" />

        <!-- Text is fetched rather than framed: an iframe would render it as
             HTML, and a `.md` full of angle brackets is not markup. -->
        <pre
          v-else-if="kind === 'Document' && text !== null"
          class="max-h-[70vh] w-full overflow-auto rounded-6 bg-surface-gray-1 p-4 text-p-xs text-ink-gray-7"
        >{{ text }}</pre>

        <div v-else class="flex flex-col items-center gap-3 text-center">
          <Icon name="lucide-file-question" class="size-10 text-ink-gray-4" />
          <p class="text-p-sm text-ink-gray-6">
            There is no preview for this kind of file.
          </p>
        </div>
      </div>
    </template>

    <template #actions>
      <Button icon-left="lucide-link" label="Share a link" @click="share" />
      <Button icon-left="lucide-download" label="Download" @click="download" />
    </template>
  </Dialog>

  <ShareLink v-model="sharing" :file="file" />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, Icon } from '@/ui'
import ShareLink from './ShareLink.vue'

const props = defineProps({
  file: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })

// Only the ones a browser can show inline. A `.docx` is a Document to the
// filter chips and has no preview, which is why the fallback exists.
const READABLE = ['txt', 'md', 'csv', 'json', 'log']

const kind = computed(() => props.file?.custom_kind || 'Other')
const url = computed(() =>
  props.file
    ? `/api/method/oneapp.oneapp_core.storage.r2.download?file=${encodeURIComponent(props.file.name)}`
    : '',
)

const text = ref(null)

// Fetched when the dialog opens rather than when the row is drawn: a list of
// forty text files must not be forty requests for content nobody looked at.
watch([open, () => props.file?.name], async ([showing]) => {
  text.value = null
  if (!showing || kind.value !== 'Document') return

  const extension = (props.file.file_name || '').split('.').pop().toLowerCase()
  if (!READABLE.includes(extension)) return

  try {
    const response = await fetch(url.value)
    text.value = (await response.text()).slice(0, 200_000)
  } catch {
    // No preview is the honest outcome, and the download button is still there.
    text.value = null
  }
})

const download = () => window.open(url.value, '_blank')

// Its own dialog rather than a panel in this one: sharing is the rarer thing
// and it has a list, a form and a destructive control of its own.
//
// And it replaces this one rather than sitting on top of it. Two open modals
// nest, and the outer one is marked `aria-hidden` while the inner is on screen
// — which is a screen reader announcing the file's name over a form it cannot
// then describe, and a keyboard user tabbing into content that is not there.
const sharing = ref(false)
function share() {
  open.value = false
  sharing.value = true
}
</script>

<!--
  A file in a dialog: a name, the thing itself, and two ways out of it.

  What is actually drawn is `FileSurface`, which the Drive's pane draws too.
  This is the chrome a mail attachment and a record's Files tab want — a modal
  over the page you were on — and the Drive wants a column beside the list
  instead, so the chrome is here and the looking is there.
-->
<template>
  <Dialog v-model="open" :title="file?.file_name || __('File')" size="4xl">
    <!--
      The title slot rather than the `title` prop, for one reason: a file a
      model drew carries the same mark here as it does in the list. `FileFace`
      says it reaches every surface by being said once, and this was the one
      surface it did not reach — the previewer takes its title as a string, so
      the mark had nowhere to go and a generated image opened unmarked.
    -->
    <template #title>
      <h3 class="flex min-w-0 items-center gap-1.5 text-2xl-semibold leading-6 text-ink-gray-8">
        <span class="truncate">{{ file?.file_name || __('File') }}</span>
        <AiMark v-if="file?._ai" :mark="file._ai" />
      </h3>
    </template>

    <template #default>
      <FileSurface :file="file" :live="open" />
    </template>

    <template #actions>
      <Button icon-left="lucide-link" :label="__('Share a link')" @click="share" />
      <Button icon-left="lucide-download" :label="__('Download')" @click="download" />
    </template>
  </Dialog>

  <ShareLink v-model="sharing" :file="file" />
</template>

<script setup>
import { ref } from 'vue'
import { Button, Dialog } from '@/ui'
import AiMark from '../AiMark.vue'
import FileSurface from './FileSurface.vue'
import ShareLink from './ShareLink.vue'
import { downloadUrl } from '@/lib/files/files'
import { __ } from '@/lib/runtime/translate'

const props = defineProps({
  file: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })

const download = () => window.open(downloadUrl(props.file.name), '_blank')

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

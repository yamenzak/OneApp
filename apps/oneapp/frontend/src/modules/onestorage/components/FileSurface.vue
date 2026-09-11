<!--
  Looking at a file without downloading it.

  Six kinds and a fallback, which is the set that covers a workspace's files.
  Everything points at the same URL — `r2.download`, which checks the reader's
  permission and then redirects to a presigned object. A `<video>` following a
  302 is a `<video>` that plays, so streaming needs nothing of ours.

  The body alone, with no chrome around it: the Drive shows this in a pane
  beside the list and a record's Files tab and a mail thread show it in a
  dialog, and what is being looked at is the same thing in all three. Whatever
  holds it owns the title and the actions, because a pane's title bar and a
  dialog's are not the same shape.
-->
<template>
  <div class="grid place-items-center" :class="tall ? 'min-h-[24rem]' : ''">
    <img
      v-if="kind === 'Image'"
      :src="url"
      :alt="file.file_name"
      class="max-h-[70vh] w-auto rounded-6 object-contain"
    />

    <!-- A PDF is the browser's own viewer. Rendering one ourselves would be
         shipping a PDF engine to save an iframe. -->
    <iframe
      v-else-if="kind === 'PDF'"
      :src="url"
      :title="file.file_name"
      class="h-[70vh] w-full rounded-6 border border-outline-gray-1"
    />

    <video
      v-else-if="kind === 'Video'"
      :src="url"
      controls
      class="max-h-[70vh] w-full rounded-6"
    />

    <audio v-else-if="kind === 'Audio'" :src="url" controls class="w-full" />

    <!-- Text is fetched rather than framed: an iframe would render it as HTML,
         and a `.md` full of angle brackets is not markup. -->
    <pre
      v-else-if="text !== null"
      class="max-h-[70vh] w-full overflow-auto rounded-6 bg-surface-gray-1 p-4 text-p-xs text-ink-gray-7"
    >{{ text }}</pre>

    <!--
      Nothing to render, which is not the same as nothing to say.

      This used to be an icon and one sentence, and a person who clicked a file
      the browser cannot draw learnt less about it than the row they clicked it
      from. So the pane answers what it can: what it is called, what kind of
      thing it is, and how big — which for the commonest reason this branch is
      reached, a file too big to open, is the whole answer.
    -->
    <div data-slot="file-details" class="flex flex-col items-center gap-3 px-4 text-center">
      <Icon :name="iconFor(file)" class="size-10 text-ink-gray-4" />
      <div class="min-w-0">
        <p class="truncate text-base font-medium text-ink-gray-8">
          {{ file?.file_name || __('File') }}
        </p>
        <p v-if="facts" class="mt-0.5 text-p-xs text-ink-gray-5">{{ facts }}</p>
      </div>
      <p class="text-p-sm text-ink-gray-6">{{ why }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Icon } from '@/ui'
import {
  TEXT_CEILING,
  downloadUrl,
  humanSize,
  iconFor,
  labelForKind,
} from '@/modules/onestorage/lib/files'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  file: { type: Object, default: null },
  /**
   * Whether this is on screen. Not the same as being mounted: a dialog keeps
   * its content in the tree while shut, and forty text files in a list must not
   * be forty requests for content nobody looked at.
   */
  live: { type: Boolean, default: false },
  /** A dialog reserves the height; a pane already has one. */
  tall: { type: Boolean, default: true },
})

// Only the ones a browser can show inline. A `.docx` is a Document to the
// filter chips and has no preview, which is why the fallback exists.
const READABLE = ['txt', 'md', 'csv', 'json', 'log']

const kind = computed(() => props.file?.custom_kind || 'Other')

/**
 * Whether the bytes can be fetched and shown as text.
 *
 * The same ceiling the editors keep, for the same reason: this reads the whole
 * object to show the top of it, and a log nobody can edit is not a log worth
 * downloading in full to look at. Over it the details block below says so.
 */
const oversize = computed(() => (Number(props.file?.file_size) || 0) > TEXT_CEILING)

/** Whether this is text at all, which is a different question from its size. */
const readable = computed(() =>
  READABLE.includes((props.file?.file_name || '').split('.').pop().toLowerCase()),
)

/** What it is and how big, for the file nothing above could draw. */
const facts = computed(() =>
  [labelForKind(kind.value), humanSize(props.file)].filter(Boolean).join(' · '),
)

// Two different refusals, and saying the wrong one is worse than saying
// nothing: a 5 MB `.docx` has no preview at any size, and telling somebody it
// is too big invites them to try a smaller one.
const why = computed(() =>
  readable.value && oversize.value
    ? __('This one is too big to show here. Download it to read it.')
    : __('There is no preview for this kind of file.'),
)

const url = computed(() => (props.file ? downloadUrl(props.file.name) : ''))

const text = ref(null)

watch([() => props.live, () => props.file?.name], async ([showing]) => {
  text.value = null
  if (!showing || !props.file) return

  // Opening a file is what makes it recent, and this is where opening happens.
  // The server stamps `custom_opened` on `details`, which nothing called — so
  // the rail's second place could never fill and was empty on every site.
  // Fired and not awaited: the preview must not wait on bookkeeping.
  workspace.driveFile(props.file.name).catch(() => {})

  if (!readable.value || oversize.value) return

  try {
    const response = await fetch(url.value)
    text.value = (await response.text()).slice(0, 200_000)
  } catch {
    // No preview is the honest outcome, and the download button is still there.
    text.value = null
  }
}, { immediate: true })
</script>

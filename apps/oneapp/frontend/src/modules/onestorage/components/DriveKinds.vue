<template>
  <!--
    "Show me every image", asked of the folder you are in.

    One query with a different `kind` — `onestorage/query.py` has taken one
    since the column existed and nothing in the browser ever sent one. This is
    the row that sends it.

    Pills and not tabs, deliberately. A tab is a *place*, and none of these is:
    they narrow what is in front of you and the breadcrumb above does not
    change. There is one tab metaphor in this product and it is the dock —
    which is also why OneCloud's window has no tab strip of its own.

    Seven and not ten. `kinds.py` knows Folder, PDF, Audio and Other as well,
    and none of the four is a question anybody asks a folder: a folder is a row
    you can see, and "show me the audio" in a workspace of drawings is a pill
    that is empty every time it is pressed. PDFs go under Documents, where a
    person looking for one would look.
  -->
  <div
    data-slot="drive-kinds"
    class="flex shrink-0 items-center gap-1 overflow-x-auto px-3 py-2"
  >
    <Button
      v-for="one in PILLS"
      :key="one.kind"
      size="sm"
      :variant="one.kind === kind ? 'subtle' : 'ghost'"
      :icon-left="one.icon"
      :label="one.label"
      :class="one.kind === kind ? '!bg-surface-gray-3' : 'text-ink-secondary'"
      :data-kind="one.kind || 'all'"
      @click="emit('pick', one.kind)"
    />
  </div>
</template>

<script setup>
import { Button } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** Which one is in force. Empty is All, which is the absence of a filter. */
  kind: { type: String, default: '' },
})

const emit = defineEmits(['pick'])

/**
 * The kinds worth a pill, in the order somebody scans them.
 *
 * `Document` is the pill and `PDF` is not, because the two are one question to
 * a person looking for a specification — see the server's list for the rest.
 * The two editors come next, because "the sheets in here" is the question a
 * workspace asks about its own work rather than about what it was sent.
 */
const PILLS = [
  { kind: '', label: __('All'), icon: 'lucide-layers' },
  { kind: 'Image', label: __('Images'), icon: 'lucide-image' },
  { kind: 'Video', label: __('Videos'), icon: 'lucide-video' },
  { kind: 'Document', label: __('Documents'), icon: 'lucide-file-text' },
  { kind: 'Sheet', label: __('Sheets'), icon: 'lucide-table' },
  { kind: 'Doc', label: __('Docs'), icon: 'lucide-pilcrow' },
  { kind: 'Code', label: __('Code'), icon: 'lucide-code' },
]
</script>

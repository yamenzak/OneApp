<!--
  One file on a message.

  This was a bare `<a href>` with a paperclip and a filename: no size, though
  the server had always sent one, and no way to look at the thing without
  downloading it first. Deciding whether to open a 40 MB drawing on a phone
  needs the size, and most of the time what somebody wants is to *look*, not
  to keep.

  Frappe Mail's capsule swaps its icon for a download arrow on hover, and that
  is the one part of their shape not worth taking: a hover affordance is not
  reachable on a touch screen, and ours does not need one. Clicking opens the
  Drive's previewer, which has Download and Share a link in its footer — so the
  shortcut would save one tap on a mouse and hide the action entirely on a
  phone.
-->
<template>
  <Button
    data-slot="mail-attachment"
    variant="outline"
    class="max-w-64"
    :icon-left="iconFor(file)"
    @click="emit('open', file)"
  >
    {{ file.file_name }}
    <template v-if="size" #suffix>
      <span class="shrink-0 text-p-xs text-ink-gray-4">{{ size }}</span>
    </template>
  </Button>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from '@/ui'

import { humanSize, iconFor } from '../../lib/files'

const props = defineProps({
  /** A `File` row: `name`, `file_name`, `file_size`, `custom_kind`. */
  file: { type: Object, required: true },
})

const emit = defineEmits(['open'])

const size = computed(() => humanSize(props.file))
</script>

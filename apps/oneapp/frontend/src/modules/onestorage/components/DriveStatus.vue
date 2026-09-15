<template>
  <!--
    How many, how much, and where it is.

    Under what it counts, which is where every file manager has put it for
    thirty years and where ours was not: the count sat at the bottom *right* of
    the list, floating, saying "50 things, more below" — a sentence about
    paging rather than a fact about the folder.

    Three facts and a separator between them, because they answer three
    different questions: how much is here, how much have I picked, and how big
    is that. The size is only said when something is chosen — the size of a
    folder is a walk, and a number that took a second to appear would be a
    number nobody trusts.
  -->
  <footer
    data-slot="drive-status"
    class="flex shrink-0 items-center gap-2 border-t border-outline-gray-2 px-3 py-1.5 text-p-xs text-ink-muted"
  >
    <span class="tabular-nums">{{ counted }}</span>
    <template v-if="picked.length">
      <span aria-hidden="true">·</span>
      <span class="tabular-nums">{{ chosen }}</span>
      <span v-if="bytes" aria-hidden="true">·</span>
      <span v-if="bytes" class="tabular-nums">{{ bytes }}</span>
    </template>

    <div class="flex-1" />

    <!-- What this place will not do, where it refuses something. A mount reads
         and does not write, and saying so under the list is cheaper than a
         reader finding out by pressing. -->
    <Tooltip v-if="note" :text="note">
      <span class="truncate">{{ note }}</span>
    </Tooltip>
  </footer>
</template>

<script setup>
import { computed } from 'vue'
import { Tooltip } from '@/ui'
import { sizeText } from '@/shared/lib/files/size'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Everything the frame has read, which is what "N items" counts. */
  rows: { type: Array, default: () => [] },
  /** And what is ticked out of it. */
  picked: { type: Array, default: () => [] },
  /** Whether there are more pages behind this one, so the count can say so. */
  more: { type: Boolean, default: false },
  /** A sentence about this place, where it has one worth saying. */
  note: { type: String, default: '' },
})

const counted = computed(() => {
  const many = props.rows.length
  if (!many) return __('Nothing here')
  if (props.more) {
    return many === 1 ? __('1 item, more below') : __('{0} items, more below', [many])
  }
  return many === 1 ? __('1 item') : __('{0} items', [many])
})

/**
 * How many are ticked.
 *
 * Said here and not on the command bar above, which holds the *verbs*: a count
 * is a fact about the list and it belongs under the list. `SelectionBar` — the
 * floating bar a record list and a mailbox draw — is the other answer to the
 * same question, and it is the right one for a surface with no status bar to
 * put it in.
 */
const chosen = computed(() => (
  props.picked.length === 1
    ? __('1 selected')
    : __('{0} selected', [props.picked.length])
))

/** The size of what is chosen, where any of it has one. A folder has none. */
const bytes = computed(() => {
  const total = props.picked.reduce((sum, file) => sum + (file.file_size || 0), 0)
  return sizeText(total)
})
</script>

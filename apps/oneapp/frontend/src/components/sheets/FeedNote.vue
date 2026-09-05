<template>
  <!--
    Where these rows came from, and whether they still follow it.

    A quotation whose line items came off a spreadsheet had, until this, no
    memory of that: the pull wrote the rows and returned a count, and a month
    later nobody could say which sheet those prices were.

    Locking is RUA's lock. After it the document is the record and the sheet is
    history — a pull is refused rather than quietly overwriting a quotation
    somebody has since corrected by hand.

    Nothing pushes, and that is the design. What this adds is *finding out*:
    when the sheet has moved on since these rows were taken, the note says so
    and the control beside it is already the one that would fix it. A sheet
    that could reprice a quotation after it was sent would make locking the
    thing you must remember rather than the thing you choose.
  -->
  <div
    data-slot="sheet-feed"
    class="flex flex-wrap items-center gap-x-2 gap-y-1 text-p-xs text-ink-gray-5"
  >
    <Icon name="lucide-table-2" class="size-3.5 shrink-0" />
    <span>
      Filled from <span class="text-ink-gray-7">{{ feed.sheet_title || feed.sheet }}</span>
      · {{ feed.label }}, {{ when }}
    </span>

    <Badge v-if="locked" theme="gray" variant="subtle" size="sm" label="Locked" />

    <!-- The whole of "following": you are told, and the button that acts on it
         is the next thing along. -->
    <Badge
      v-if="feed.stale"
      theme="amber"
      variant="subtle"
      size="sm"
      label="The sheet has changed since"
    />
    <Badge
      v-else-if="feed.sheet_gone"
      theme="gray"
      variant="subtle"
      size="sm"
      label="That sheet is gone"
    />

    <!-- The one thing worth doing about it, and only for somebody who may
         change the record. Reading who filled it is not the same right as
         deciding the sheet no longer feeds it. -->
    <Button
      v-if="editable"
      size="sm"
      variant="ghost"
      :icon-left="locked ? 'lucide-unlock' : 'lucide-lock'"
      :label="locked ? 'Follow the sheet again' : 'Lock these rows'"
      :loading="busy"
      @click="toggle"
    />

    <span v-if="feed.skipped" class="basis-full text-ink-amber-4">
      {{ feed.skipped }} had no matching field and {{ many ? 'were' : 'was' }} left out.
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Icon, dayjsLocal } from '@/ui'

import { workspace } from '../../lib/workspace'

const props = defineProps({
  feed: { type: Object, required: true },
  editable: { type: Boolean, default: false },
})

const emit = defineEmits(['changed'])

const busy = ref(false)

const locked = computed(() => props.feed.status === 'Locked')
const many = computed(() => String(props.feed.skipped || '').includes(','))

const when = computed(() => {
  const at = locked.value ? props.feed.locked_on : props.feed.pulled_on
  return at ? dayjsLocal(at).fromNow() : 'just now'
})

async function toggle() {
  busy.value = true
  try {
    const done = locked.value
      ? await workspace.sheetUnlock(props.feed.reference_doctype, props.feed.reference_name, props.feed.into)
      : await workspace.sheetLock(props.feed.reference_doctype, props.feed.reference_name, props.feed.into)
    emit('changed', done)
  } finally {
    busy.value = false
  }
}
</script>

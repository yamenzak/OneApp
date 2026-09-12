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
    class="flex flex-wrap items-center gap-x-2 gap-y-1 text-p-xs text-ink-muted"
  >
    <Icon name="lucide-table-2" class="size-3.5 shrink-0" />
    <span>
      {{ __('Filled from {0}', [feed.sheet_title || feed.sheet]) }}
      · {{ feed.label }}, {{ when }}
    </span>

    <Badge v-if="locked" theme="gray" variant="subtle" size="sm" :label="__('Locked')" />

    <!-- The whole of "following": you are told, and the button that acts on it
         is the next thing along. -->
    <Badge
      v-if="feed.stale"
      theme="amber"
      variant="subtle"
      size="sm"
      :label="__('The sheet has changed since')"
    />
    <Badge
      v-else-if="feed.sheet_gone"
      theme="gray"
      variant="subtle"
      size="sm"
      :label="__('That sheet is gone')"
    />

    <!--
      The control that acts on the sentence, beside the sentence. It used to be
      a button in the header two rows up — you were told the sheet had changed
      here and the thing to press about it was somewhere else.

      No picker: the table is bound to one sheet and one range, so "again"
      names them both. It is still a press, because a quotation is a commitment
      and a rate edited at six o'clock must not move a number a customer agreed
      to.
    -->
    <Button
      v-if="editable && !locked && feed.stale"
      size="sm"
      variant="subtle"
      icon-left="lucide-refresh-cw"
      :label="__('Fill again')"
      :loading="filling"
      @click="fillAgain"
    />

    <!-- The one thing worth doing about it, and only for somebody who may
         change the record. Reading who filled it is not the same right as
         deciding the sheet no longer feeds it. -->
    <Button
      v-if="editable"
      size="sm"
      variant="ghost"
      :icon-left="locked ? 'lucide-unlock' : 'lucide-lock'"
      :label="locked ? __('Follow the sheet again') : __('Lock these rows')"
      :loading="busy"
      @click="toggle"
    />

    <span v-if="feed.skipped" class="basis-full text-ink-amber-4">
      {{
        many
          ? __('{0} had no matching field and were left out.', [feed.skipped])
          : __('{0} had no matching field and was left out.', [feed.skipped])
      }}
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Icon } from '@/ui'

import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'

const props = defineProps({
  feed: { type: Object, required: true },
  editable: { type: Boolean, default: false },
})

const emit = defineEmits(['changed', 'filled'])

const filling = ref(false)

/**
 * Take the rows again, from the sheet and range this table is already bound
 * to. `pull` replaces rather than appends, so pressing it twice cannot double
 * a quotation — and it refuses outright once the table is locked, which is why
 * the button is not drawn then.
 */
async function fillAgain() {
  filling.value = true
  try {
    const done = await workspace.sheetPull(props.feed.sheet, {
      label: props.feed.label,
      doctype: props.feed.reference_doctype,
      docname: props.feed.reference_name,
      into: props.feed.into,
    })
    emit('filled', done)
  } finally {
    filling.value = false
  }
}

const busy = ref(false)

const locked = computed(() => props.feed.status === 'Locked')
const many = computed(() => String(props.feed.skipped || '').includes(','))

const when = computed(() => {
  const at = locked.value ? props.feed.locked_on : props.feed.pulled_on
  return at ? ago(at) : __('just now')
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

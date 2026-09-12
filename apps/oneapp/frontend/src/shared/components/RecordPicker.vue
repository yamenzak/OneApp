<!--
  Which record is this about?

  Asked once, at the moment a bound template is used — a covering-letter
  template is for *any* quotation, so the first thing it needs is which one.
  After that the answer is the file's binding and nothing asks again.

  One component for both editors, because it is one question. The search is
  the server's, through `shared.binding.records`, which runs the caller's own
  permissions: what somebody sees here is what they could have opened, User
  Permissions included.
-->
<template>
  <Picker
    v-model="open"
    :title="__('Which {0}?', [doctype])"
    :said="said"
    :source="look"
    :placeholder="__('Search')"
    :empty-title="__('Nothing matched')"
    size="md"
    @pick="take"
  >
    <template #option="{ one }">
      <!-- The title first and the id under it, because a person is looking
           for the Halloway job rather than for SAL-QTN-2025-00005 — and still
           needs to see which one they picked. -->
      <span class="flex min-w-0 flex-col">
        <span class="truncate text-sm text-ink-primary">{{ one.title || one.name }}</span>
        <span v-if="one.title && one.title !== one.name" class="truncate text-xs text-ink-muted">
          {{ one.name }}
        </span>
      </span>
    </template>
  </Picker>
</template>

<script setup>
import Picker from '@/shared/components/Picker.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The record kind to search. Empty means the dialog has nothing to ask. */
  doctype: { type: String, default: '' },
  /** One sentence saying what choosing will do, in the caller's words. */
  said: { type: String, default: '' },
})

const emit = defineEmits(['pick'])

const open = defineModel({ type: Boolean, default: false })

const look = async (asked) =>
  props.doctype ? (await workspace.bindableRecords(props.doctype, asked)) || [] : []

const take = (row) =>
  emit('pick', { doctype: props.doctype, name: row.name, title: row.title || row.name })
</script>

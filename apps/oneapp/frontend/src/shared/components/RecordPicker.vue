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
  <Dialog v-model="open" :title="__('Which {0}?', [doctype])">
    <template #default>
      <div class="flex flex-col gap-3">
        <p class="text-p-sm text-ink-secondary">{{ said }}</p>

        <Combobox
          v-model="chosen"
          v-model:query="query"
          :options="options"
          :placeholder="__('Search')"
          :loading="loading"
          :filterable="false"
          :empty-text="loading ? __('Looking…') : __('Nothing matched')"
          @update:model-value="take"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Combobox, Dialog } from '@/ui'
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

const query = ref('')
const chosen = ref('')
const options = ref([])
const loading = ref(false)

//: Long enough that typing an id is one search rather than eleven, short
//: enough that the list has moved by the time the eye reaches it.
const PAUSE = 250
let waiting = null

async function look() {
  if (!props.doctype) return
  loading.value = true
  try {
    const rows = await workspace.bindableRecords(props.doctype, query.value)
    // `label` is the title and `description` the id, because a person is
    // looking for the Halloway job rather than for SAL-QTN-2025-00005 — and
    // still needs to see which one they picked.
    options.value = (rows || []).map((row) => ({
      label: row.title || row.name,
      value: row.name,
      description: row.title && row.title !== row.name ? row.name : '',
    }))
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

function later() {
  window.clearTimeout(waiting)
  waiting = window.setTimeout(look, PAUSE)
}

watch(query, later)
watch(
  () => [open.value, props.doctype],
  ([showing]) => {
    if (!showing) return
    query.value = ''
    chosen.value = ''
    look()
  },
)

function take(name) {
  if (!name) return
  const row = options.value.find((one) => one.value === name)
  emit('pick', { doctype: props.doctype, name, title: row?.label || name })
  open.value = false
}
</script>

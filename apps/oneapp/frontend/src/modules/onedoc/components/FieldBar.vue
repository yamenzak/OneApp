<!--
  What this document is written about, and the three things you can do about it.

  Only drawn for a bound document — most documents are prose about nothing and
  should not carry a strip saying so. When it is drawn it answers the question
  the design turns on before anybody asks it: *is this fresh?* It says which
  record, and when the numbers in the prose were last read off it.

  Insert puts a token where the cursor is. Refresh asks again. Fix stops
  asking, permanently, which is what a document about to be sent wants — a
  quotation the customer received is a fact about a day, not a view onto a
  record that has moved on. See `modules/onedoc/lib/recordField.js` and
  `oneapp/onedoc/fields.py`.
-->
<template>
  <div
    class="flex shrink-0 flex-wrap items-center gap-2 border-b border-outline-gray-1 bg-surface-gray-1 px-4 py-1.5"
  >
    <Icon name="lucide-link" class="size-3.5 shrink-0 text-ink-gray-5" />
    <span class="min-w-0 truncate text-p-xs text-ink-gray-6">
      {{ __('About {0}', [bound.name || bound.doctype]) }}
    </span>
    <span class="text-p-xs text-ink-gray-4">{{ read }}</span>

    <span class="flex-1" />

    <Dropdown v-if="canWrite" :options="choices">
      <Button
        variant="ghost"
        size="sm"
        icon-left="plus"
        :label="__('Insert a field')"
        :loading="listing"
        data-slot="fields-insert"
      />
    </Dropdown>
    <Button
      variant="ghost"
      size="sm"
      icon="lucide-refresh-cw"
      :label="__('Read the record again')"
      :tooltip="__('Read the record again')"
      :loading="asking"
      data-slot="fields-refresh"
      @click="refresh"
    />
    <Button
      v-if="canWrite"
      variant="ghost"
      size="sm"
      :label="__('Fix the fields')"
      :tooltip="__('Stop asking, and keep what they say now')"
      data-slot="fields-settle"
      @click="settle"
    />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dropdown, Icon } from '@/ui'
import { applyRecordFields, namedFields } from '@/modules/onedoc/lib/recordField'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The document's File id. */
  name: { type: String, required: true },
  /** `{doctype, name}` — see `shared/binding.py`. */
  bound: { type: Object, required: true },
  /** The tiptap instance the tokens live in. */
  editor: { type: Object, default: null },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['settled'])

const asking = ref(false)
const listing = ref(false)
const offered = ref([])
const at = ref(null)

/*
 * When the numbers on screen were read.
 *
 * The whole point of the strip. A document open since this morning shows
 * this morning's total, and saying so is the difference between a reader who
 * presses Refresh and one who quotes a stale number down the phone.
 */
const read = computed(() => {
  if (!at.value) return ''
  return __('as of {0}', [at.value.toLocaleTimeString()])
})

async function refresh() {
  asking.value = true
  try {
    // What is on screen, not what is on disk — the save is debounced, and a
    // field somebody just inserted is only in the editor.
    const answer = await workspace.docFields(props.name, namedFields(props.editor))
    applyRecordFields(props.editor, answer?.fields || {})
    at.value = new Date()
  } finally {
    asking.value = false
  }
}

/*
 * The fields this doctype will answer.
 *
 * Fetched when the strip appears rather than when the menu is opened, which
 * was the first attempt and does not work: the trigger's click belongs to the
 * Dropdown, so the fetch never started and the menu sat on "Looking…". One
 * small request per bound document is the price of the menu being right the
 * first time it is opened.
 */
async function list() {
  if (offered.value.length || listing.value || !props.bound.doctype) return
  listing.value = true
  try {
    offered.value = (await workspace.bindableFields(props.bound.doctype)) || []
  } finally {
    listing.value = false
  }
}

const choices = computed(() =>
  offered.value.length
    ? offered.value.map((one) => ({
        label: one.label || one.fieldname,
        onClick: () => insert(one),
      }))
    // The menu opens on the same click that starts the fetch, so the empty
    // moment is real and needs a word in it rather than a blank panel.
    : [{ label: __('Looking…'), onClick: () => {} }],
)

function insert(field) {
  props.editor
    ?.chain()
    .focus()
    .insertRecordField({ field: field.fieldname, label: field.label })
    .run()
  // Straight away, so the token shows a number rather than an em dash for as
  // long as it takes somebody to notice.
  refresh()
}

async function settle() {
  const answer = await workspace.docSettleFields(props.name)
  if (answer?.content) emit('settled', answer.content)
}

// Opened once when the strip appears, so the numbers are this minute's rather
// than the last save's — a document saved on Friday and opened on Monday is
// the ordinary case, not the strange one.
watch(
  () => props.editor,
  (instance) => {
    if (!instance) return
    refresh()
    list()
  },
  { immediate: true },
)

defineExpose({ refresh, list })
</script>

<template>
  <!--
    A long field, given the room a document gets.

    The same editor and the same toolbar the document surface uses, over the
    *field's* value — it saves back to the field and nothing becomes a file.
    That distinction is the whole design: a quotation's terms are part of the
    quotation and part of what its print format renders, and turning them into
    an attachment would change what a quotation is. A scope of works is a
    different thing and belongs in the Drive, which is `docs.make`.

    Applied on Save rather than as you type. A box this size invites rewriting
    a clause and thinking better of it, and Cancel has to mean cancel.
  -->
  <Dialog v-model="open" :title="label" size="5xl">
    <!-- The mark and the product name, then the field — as OneCode's dialog
         does, and as every editor's own corner does when it is a page. -->
    <template #title><EditorTitle brand="onedoc" :name="label" /></template>

    <template #default>
      <div class="rounded-6 border border-outline-gray-2">
        <Editor
          v-model="draft"
          :extensions="EXTENSIONS"
          :format="format"
          :editable="!disabled"
          :upload-function="uploadFunction"
        >
          <template #default="{ editor }">
            <EditorFixedMenu
              v-if="!disabled"
              :editor="editor"
              :items="documentToolbar"
              class="shrink-0 overflow-x-auto overflow-y-hidden border-b border-outline-gray-1 px-3 py-1.5"
            />
            <EditorTableMenu v-if="!disabled" :editor="editor" />
            <div class="max-h-[65vh] overflow-y-auto px-6 py-6">
              <div class="mx-auto w-full max-w-page">
                <EditorContent
                  :editor="editor"
                  :aria-label="label"
                  dir="auto"
                  class="prose prose-sm max-w-none"
                />
              </div>
            </div>
          </template>
        </Editor>
      </div>
    </template>

    <template #actions>
      <Button v-if="!disabled" variant="solid" :label="__('Save')" @click="apply" />
      <Button :label="__('Cancel')" @click="open = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

import {
  Button,
  Dialog,
  Editor,
  EditorContent,
  EditorFixedMenu,
  EditorTableMenu,
  RichTextKit,
} from '@/ui'
import EditorTitle from '@/shared/components/brand/EditorTitle.vue'
import { documentToolbar } from '@/modules/onedoc/components/toolbar'
import { __ } from '@/shared/lib/runtime/translate'

const EXTENSIONS = [RichTextKit]

const open = defineModel({ type: Boolean, default: false })

const props = defineProps({
  value: { type: [String, Object], default: '' },
  label: { type: String, default: '' },
  // 'html' | 'json' | 'markdown' — the same one the field itself stores, or
  // what comes back is not what the record asked for.
  format: { type: String, default: 'html' },
  disabled: { type: Boolean, default: false },
  uploadFunction: { type: Function, default: undefined },
})

const emit = defineEmits(['apply'])

const draft = ref(props.value)

function apply() {
  emit('apply', draft.value)
  open.value = false
}

// Opened again after the field moved on — a fetch_from filling it, somebody
// else saving — so the draft starts from what the record says rather than from
// the last look at it.
watch(open, (showing) => {
  if (showing) draft.value = props.value
})
</script>

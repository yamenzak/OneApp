<template>
  <!--
    A code field, given the room a file gets. OneCode.

    The same editor the Drive opens a `.py` in, over the *field's* value — it
    saves back to the field and nothing becomes a file. That distinction is the
    same one `LongTextDialog` makes and it matters for the same reason: a
    print format's Jinja is part of the print format, and turning it into an
    attachment would change what a print format is.

    Applied on Save rather than as you type. A box this size invites rewriting
    a rule and thinking better of it, and Cancel has to mean cancel.
  -->
  <Dialog v-model="open" :title="label" size="5xl">
    <!-- The mark and the product name, then the field. A dialog that is one of
         our editors says which one it is, the same way the editor's own corner
         does when it is a page. -->
    <template #title><EditorTitle brand="onecode" :name="label" /></template>

    <template #default>
      <!-- The class is on the wrapper and not on `CodeEditor`. Scoped CSS
           reaches a child component's root, and `.tall :deep(.cm-editor)` is a
           *descendant* selector: CodeEditor's root is the `.cm-editor` itself,
           so the rule matched nothing and the box stayed eight lines tall. -->
      <div class="tall overflow-hidden rounded-6 border border-outline-gray-2">
        <CodeEditor
          v-model="draft"
          :language="language || 'plain'"
          :disabled="disabled"
          variant="subtle"
          size="md"
          :aria-label="label"
        />
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

import { Button, CodeEditor, Dialog } from '@/ui'
import EditorTitle from '@/shared/components/brand/EditorTitle.vue'
import { __ } from '@/shared/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })

const props = defineProps({
  value: { type: String, default: '' },
  label: { type: String, default: '' },
  /** A `loadLanguage` key. Blank opens it uncoloured, which is not an error. */
  language: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
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
watch(open, (showing) => { if (showing) draft.value = props.value })
</script>

<style scoped>
/*
 * A fixed tall box rather than one that grows with the content. The point of
 * this dialog is the room: a field opened here should be the same size before
 * and after somebody deletes half of it, so the Save button does not walk up
 * the screen while they are reading.
 */
.tall :deep(.cm-editor) {
  height: 65vh;
  max-height: none;
}

.tall :deep(.cm-scroller) {
  overflow: auto;
}
</style>

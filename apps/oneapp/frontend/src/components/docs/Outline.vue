<template>
  <!--
    Where you are in a long document.

    Derived from the editor's own document on every transaction rather than
    from a table-of-contents extension. frappe-ui ships one, and it inserts a
    ToC *into* the page — which is a block somebody puts in a report, not a
    rail that follows the cursor. Reading the headings is a walk over the top
    level of the doc, which is cheap enough to do on every keystroke and always
    describes the text that is actually there.
  -->
  <nav
    v-if="headings.length > 1"
    aria-label="Outline"
    class="hidden w-56 shrink-0 border-e border-outline-gray-1 lg:block"
  >
    <FadedScroll class="max-h-full">
      <div class="flex flex-col gap-0.5 p-3">
        <p class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          Outline
        </p>
        <Button
          v-for="one in headings"
          :key="one.id"
          variant="ghost"
          class="w-full !justify-start !px-2"
          :label="one.text"
          @click="go(one)"
        >
          <span
            class="w-full truncate text-left text-p-sm"
            :class="[
              one.level > 2 ? 'ps-3 text-ink-gray-6' : 'text-ink-gray-7',
              one.id === active ? 'font-medium text-ink-gray-8' : '',
            ]"
          >{{ one.text }}</span>
        </Button>
      </div>
    </FadedScroll>
  </nav>
</template>

<script setup>
import { computed, ref } from 'vue'

import { Button } from '@/ui'
import FadedScroll from '../FadedScroll.vue'

const props = defineProps({
  editor: { type: Object, default: null },
  // Bumped by the host on every transaction. A ref to the editor is not
  // reactive in itself — ProseMirror mutates its own state in place — so
  // something outside has to say "it changed", and the host is already told.
  revision: { type: Number, default: 0 },
})

const active = ref('')

const headings = computed(() => {
  // Read so the computed re-runs when the host says the document moved.
  void props.revision
  const doc = props.editor?.state?.doc
  if (!doc) return []

  const found = []
  doc.descendants((node, pos) => {
    if (node.type.name !== 'heading') return
    const text = node.textContent.trim()
    if (text) found.push({ id: node.attrs.id || `h-${pos}`, pos, level: node.attrs.level, text })
  })
  return found
})

function go(one) {
  active.value = one.id
  const editor = props.editor
  if (!editor) return

  // Through the editor rather than through `getElementById`: a heading has an
  // id only where frappe-ui's HeadingIds extension gave it one, and the
  // position is what the editor itself uses to scroll.
  editor.chain().focus().setTextSelection(one.pos + 1).scrollIntoView().run()
}
</script>

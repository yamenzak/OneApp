<!--
  The verbs, on a message being written.

  It lived in `shared/` and was one menu for mail, the writer and the sheet.
  It is mail's now, because mail is the one surface where the verbs are a
  control of their own: an editor keeps them in the menu it already has —
  which is where the workbook always kept them and where the writer's went
  when OneAI stopped being something every app had a separate door to.

  The words and their order did not come with it. They are
  `shared/lib/ai/verbs.js`, so "Improve" means the same thing and sits in the
  same place in a composer and in a document — which was the reason this was
  one component, and is the part of it worth keeping.

  What the menu offers is what the *server* declares (`onespace/ai/text.py`),
  fetched once for the whole session. A surface may narrow that with `verbs` —
  a cell has nothing to proofread — and may not widen it: a verb this asks for
  that nothing declares is refused at the endpoint, and drawing it would be
  teaching somebody a thing that does not work.

  Nothing is drawn at all where the workspace has switched writing help off or
  the site has no gateway. A menu whose every item answers "switched off" is
  worse than no menu.
-->
<template>
  <Dropdown v-if="options.length" :options="options" :align="align">
    <!--
      The mark keeps its word on a desktop and loses it on a phone — §D4.
      "Write with Rua" is four times the width of the glyph and it was taking
      that width out of the document's own title at 390px. `label` stays
      either way: on an icon-only `Button` it is the accessible name, which is
      the pattern every other icon button here uses.
    -->
    <Button
      :variant="variant"
      :icon="phone ? 'lucide-sparkles' : undefined"
      :icon-left="phone ? undefined : 'lucide-sparkles'"
      :label="label || __('Write with {0}', [assistantName])"
      :loading="busy"
      :disabled="disabled"
      data-slot="ai-menu"
    />
  </Dropdown>

  <!--
    "Write…" is the one verb with nothing to work on yet, so it is the one
    that has to ask. A dialog rather than an inline field: it is a sentence
    somebody composes, and a one-line input in a toolbar is where a sentence
    gets abandoned half-typed.
  -->
  <Dialog v-model="asking" :title="__('What should it say?')" size="lg">
    <template #default>
      <FormControl
        v-model="instruction"
        type="textarea"
        :rows="4"
        :placeholder="__('Tell them the survey is booked for Tuesday and ask who will meet us on site.')"
        data-slot="ai-instruction"
        @keydown.enter.meta="write()"
        @keydown.enter.ctrl="write()"
      />
      <p class="mt-2 text-p-xs text-ink-muted">
        {{ __('It writes from what is on this screen and invents nothing. Check it before it goes out.') }}
      </p>
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Write it')"
        :disabled="!instruction.trim()"
        @click="write()"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, Dropdown, FormControl } from '@/ui'

import { writingOptions, writingVerbs } from '@/shared/lib/ai/verbs'
import { __ } from '@/shared/lib/runtime/translate'
import { assistantName } from '@/modules/onespace/lib/shell/assistant'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'

const props = defineProps({
  /**
   * Which verbs this surface has any use for, narrowing what the server
   * declares. Empty means all of them.
   */
  verbs: { type: Array, default: () => [] },
  /** There is nothing to work on — an empty composer, no selection. */
  disabled: { type: Boolean, default: false },
  /** Something is already being written. */
  busy: { type: Boolean, default: false },
  label: { type: String, default: '' },
  variant: { type: String, default: 'subtle' },
  align: { type: String, default: 'start' },
})

const emit = defineEmits(['ask'])

const phone = useIsMobile()

const declared = writingVerbs()

const asking = ref(false)
const instruction = ref('')

// The words and their order are `lib/ai/verbs.js`, because this is no longer
// the only menu that draws them — the writer keeps its verbs in the editor's
// own menu since its AI button left the chrome.
const options = computed(() => writingOptions(declared, {
  narrow: props.verbs,
  ask: (one) => emit('ask', one),
  write: open,
}))

function open() {
  instruction.value = ''
  asking.value = true
}

function write() {
  const said = instruction.value.trim()
  if (!said) return
  asking.value = false
  emit('ask', { verb: 'write', instruction: said })
}
</script>

<!--
  The verbs, wherever there is a passage to do one of them to.

  One menu for mail, the writer and the sheet. Not because the code would
  otherwise be duplicated — it is twenty lines — but because these are the
  words a person learns once. "Improve" has to mean the same thing and sit in
  the same place in a composer, a document and a cell, or it is three features
  that happen to share a prompt.

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
  <Dropdown v-if="offered.length" :options="options" :align="align">
    <Button
      :variant="variant"
      icon-left="lucide-sparkles"
      :label="label || __('Write with AI')"
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

import { writingVerbs } from '@/shared/lib/ai/verbs'
import { __ } from '@/shared/lib/runtime/translate'

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

const declared = writingVerbs()

/** What the server declares, narrowed by what this surface asked for. */
const offered = computed(() => {
  if (!declared.rewrite) return []
  const wanted = props.verbs.length ? props.verbs : declared.verbs
  return declared.verbs.filter((one) => wanted.includes(one))
})

/**
 * What each verb is called on screen.
 *
 * Here and not on the server: the server's `VERBS` are keys and the
 * instructions behind them, and neither is a label — one is machine-facing
 * and the other is written at a model. These are written at a person, and
 * they are the strings that get translated.
 */
const WORDS = {
  write: [__('Write…'), 'lucide-pen-line'],
  improve: [__('Improve'), 'lucide-wand-sparkles'],
  proofread: [__('Proofread'), 'lucide-spell-check'],
  shorten: [__('Make it shorter'), 'lucide-minimize-2'],
  expand: [__('Make it longer'), 'lucide-maximize-2'],
}

/** And the six registers, which are one verb with an argument. */
const TONES = {
  formal: __('More formal'),
  friendly: __('Friendlier'),
  direct: __('More direct'),
  warm: __('Warmer'),
  apologetic: __('Apologetic'),
  firm: __('Firmer'),
}

const asking = ref(false)
const instruction = ref('')

const options = computed(() => {
  // Ordered by `WORDS` rather than by what the server listed. Which verbs
  // exist is the server's; the order they are read in is a question about a
  // menu, and Write comes first because on an empty message it is the only
  // one that does anything.
  const plain = Object.keys(WORDS)
    .filter((one) => one !== 'tone' && offered.value.includes(one))
    .map((one) => ({
      label: WORDS[one][0],
      icon: WORDS[one][1],
      onClick: () => (one === 'write' ? open() : emit('ask', { verb: one })),
    }))

  const groups = [{ group: '', hideLabel: true, options: plain }]

  // A group rather than a submenu, because the menu has no submenus and six
  // items under a heading is what a submenu would have shown anyway.
  if (offered.value.includes('tone')) {
    groups.push({
      group: __('Tone'),
      options: declared.tones
        .filter((one) => TONES[one])
        .map((one) => ({
          label: TONES[one],
          onClick: () => emit('ask', { verb: 'tone', tone: one }),
        })),
    })
  }
  return groups
})

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

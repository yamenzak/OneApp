<template>
  <!--
    This value was written by a model.

    One component wherever it is said — beside a field's label, on a file row,
    over a generated image — so the mark reads the same everywhere and there is
    one place to change what it looks like.

    A tooltip and not a line of text: the mark is a fact about the value, not
    part of it, and a sentence beside every AI-written field would crowd out
    the thing the reader came for. The sentence is there for whoever asks.
  -->
  <Tooltip :text="said">
    <span
      class="lucide-sparkles size-3.5 shrink-0 text-ink-amber-4"
      data-slot="ai-mark"
      :aria-label="said"
      role="img"
    />
  </Tooltip>
</template>

<script setup>
import { computed } from 'vue'
import { Tooltip } from '@/ui'
import { __ } from '@/lib/runtime/translate'
import { assistantName } from '@/lib/shell/assistant'

const props = defineProps({
  /** `{ feature, model, by, when }` from the record's `_ai`. */
  mark: { type: Object, default: () => ({}) },
})

/**
 * What the mark says, in one sentence.
 *
 * Built from what is known rather than from a template with blanks: an old row
 * may carry no model, and "written by  with " is worse than the short version.
 * The assistant's own name is used because that is what this workspace calls
 * the thing that wrote it.
 */
const said = computed(() => {
  const who = assistantName.value
  return props.mark?.model
    ? __('Written by {0}, using {1}.', [who, props.mark.model])
    : __('Written by {0}.', [who])
})
</script>

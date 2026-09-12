<template>
  <!--
    Something a model has asked for, and the button that makes it happen.

    This card is the whole reason a model is allowed near a write. It cannot
    do anything; it can put one of these in front of somebody. So the card has
    to show what would actually happen, not a sentence about it — every field,
    what it says now, what it would say — because the thing being agreed to is
    the diff and a summary of a diff is not the diff.

    One card for every kind, the same way there is one doctype: a record
    change, a diary entry and a task are three different payloads and one
    decision, and three cards would be three answers to what Proposed looks
    like. What differs per kind is the icon, the words and the rows, and all
    three come from the handler — see `onespace/ai/actions.py`.

    Old value struck through, new value beside it. Two columns were tried and
    are wrong at 384px: the panel is narrow, a value can be a paragraph, and a
    table there wraps into something less readable than a line.

    Once answered it stays, greyed, saying what happened. A card that vanished
    on Apply would leave an answer above it claiming to have asked for
    something with no sign of what became of it.
  -->
  <div
    data-slot="suggestion"
    class="rounded-6 border p-3"
    :class="pending
      ? 'border-outline-gray-2 bg-surface-gray-1'
      : 'border-outline-gray-1 bg-surface-base'"
  >
    <div class="flex items-start gap-2">
      <Icon
        :name="pending ? (suggestion.icon || 'lucide-sparkles') : mark.icon"
        class="mt-0.5 size-4 shrink-0"
        :class="pending ? 'text-ink-secondary' : mark.tone"
        :aria-hidden="true"
      />
      <p class="min-w-0 flex-1 text-p-sm font-medium text-ink-primary">
        {{ suggestion.summary }}
      </p>
    </div>

    <dl class="mt-2 flex flex-col gap-1">
      <div
        v-for="(row, at) in suggestion.rows || []"
        :key="at"
        class="flex flex-wrap items-baseline gap-x-2 text-p-xs"
      >
        <dt class="text-ink-muted">{{ row.label }}</dt>
        <dd v-if="said(row.was)" class="text-ink-gray-4 line-through">
          {{ said(row.was) }}
        </dd>
        <dd class="min-w-0 break-words font-medium text-ink-primary">
          {{ said(row.now) || __('empty') }}
        </dd>
      </div>
    </dl>

    <div v-if="pending" class="mt-3 flex items-center gap-2">
      <Button
        variant="solid"
        :label="__('Apply')"
        data-slot="suggestion-apply"
        :loading="busy === 'apply'"
        :disabled="!!busy"
        @click="answer('apply')"
      />
      <Button
        :label="__('Discard')"
        data-slot="suggestion-discard"
        :loading="busy === 'discard'"
        :disabled="!!busy"
        @click="answer('discard')"
      />
    </div>

    <p v-else class="mt-2 text-p-xs" :class="mark.tone">{{ mark.said }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Icon } from '@/ui'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /**
   * One row as `actions.for_session` / `actions.for_about` returns it:
   * `{name, kind, state, summary, label, icon, rows, error}`, where a row is
   * `{label, was, now}`. `was` is absent on anything being made rather than
   * changed, which is what makes the strike-through appear only where there
   * is something to strike.
   */
  suggestion: { type: Object, required: true },
})

const emit = defineEmits(['answered'])

const busy = ref('')

const pending = computed(() => props.suggestion.state === 'Proposed')

/** What a card that has been answered says about itself. */
const mark = computed(() => ({
  Applied: { icon: 'lucide-check', tone: 'text-ink-green-3', said: __('Applied') },
  Discarded: { icon: 'lucide-x', tone: 'text-ink-muted', said: __('Discarded') },
  Failed: {
    icon: 'lucide-triangle-alert',
    tone: 'text-ink-red-3',
    said: props.suggestion.error || __('That could not be done.'),
  },
}[props.suggestion.state] || { icon: 'lucide-circle', tone: 'text-ink-muted', said: '' }))

/**
 * A stored value as a person reads it.
 *
 * Nothing clever: a value on this card came out of a record and goes back into
 * one, and reformatting it here would mean the card and the field showing
 * different spellings of the same thing.
 */
const said = (value) => {
  if (value === null || value === undefined || value === '') return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

async function answer(how) {
  if (busy.value) return
  busy.value = how
  try {
    await (how === 'apply'
      ? workspace.applySuggestion(props.suggestion.name)
      : workspace.discardSuggestion(props.suggestion.name))
    emit('answered')
  } finally {
    busy.value = ''
  }
}
</script>

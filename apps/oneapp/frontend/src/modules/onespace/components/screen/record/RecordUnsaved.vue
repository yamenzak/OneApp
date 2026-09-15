<template>
  <!--
    What you have changed and not saved, and the two things to do about it.

    A Save button says that *something* changed. On a record with forty fields
    across six groups, finding out what means opening each group and reading —
    so this says it: how many, which ones, and from what to what.

    A bar rather than a column, for the reason `RecordBand` is one: a
    permanent 288px sidebar to hold something that is usually not there is the
    pane's arithmetic again. This costs a row, it costs it only while there is
    something to save, and it is the only place Save is drawn.

    Folded to the names by default and opened to the values on press. The names
    are the question people actually have — "what did I touch" — and the values
    are the follow-up.
  -->
  <div
    data-slot="record-unsaved"
    class="flex shrink-0 flex-col gap-2 border-b border-outline-amber-1 bg-surface-amber-1 px-4 py-2"
  >
    <div class="flex items-center gap-3">
      <!-- The count first, because it is the whole headline. -->
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a row of prose that folds, not a control; a <Button> brings a height, a padding and a hover ground into a band that already has all three -->
      <button
        type="button"
        data-slot="unsaved-toggle"
        class="flex min-w-0 flex-1 items-center gap-2 text-start"
        :aria-expanded="open"
        @click="open = !open"
      >
        <Icon
          :name="open ? 'lucide-chevron-down' : 'lucide-chevron-right'"
          class="size-4 shrink-0 text-ink-amber-7"
          aria-hidden="true"
        />
        <span class="shrink-0 text-sm font-medium text-ink-amber-7">
          {{ changes.length === 1
            ? __('1 change not saved')
            : __('{0} changes not saved', [String(changes.length)]) }}
        </span>
        <!-- The names, folded. Enough to recognise what you did without
             opening anything, and truncated rather than wrapped: this is a bar
             and a bar that grows to three lines is a panel. -->
        <span v-if="!open" class="min-w-0 truncate text-sm text-ink-secondary">
          {{ named }}
        </span>
      </button>

      <div class="flex shrink-0 items-center gap-2">
        <Button
          variant="solid"
          :label="__('Save')"
          :loading="saving"
          data-slot="unsaved-save"
          @click="emit('save')"
        />
        <Button
          variant="ghost"
          :label="__('Discard')"
          :disabled="saving"
          data-slot="unsaved-discard"
          @click="emit('discard')"
        />
      </div>
    </div>

    <!-- Opened: what each one was and what it is about to be. -->
    <dl v-if="open" data-slot="unsaved-diff" class="flex flex-wrap gap-x-6 gap-y-1.5 ps-6">
      <div v-for="one in changes" :key="one.field" class="flex min-w-0 items-baseline gap-1.5">
        <dt class="shrink-0 text-xs text-ink-muted">{{ one.label }}</dt>
        <dd class="flex min-w-0 items-baseline gap-1.5 text-sm">
          <!-- Struck rather than red: what is going is not an error, and a red
               line beside a green one reads as a warning about the change
               rather than as its two halves. -->
          <span v-if="one.was" class="max-w-40 truncate text-ink-muted line-through">
            {{ one.was }}
          </span>
          <span v-if="one.was" class="shrink-0 text-ink-gray-4" aria-hidden="true">→</span>
          <span class="max-w-40 truncate text-ink-primary">{{ one.now || __('(empty)') }}</span>
        </dd>
      </div>
    </dl>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { Button, Icon } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** `[{field, label, was, now}]` — worked out by the record, which is where
   *  the form and the saved values both are. */
  changes: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'discard'])

const open = ref(false)

/** The field names, folded. Four and then a count: past four the bar is a list
 *  nobody reads, and the number is the more useful end of it. */
const SHOWN = 4

const named = computed(() => {
  const labels = props.changes.map((one) => one.label)
  if (labels.length <= SHOWN) return labels.join(', ')
  return `${labels.slice(0, SHOWN).join(', ')} ${__('and {0} more', [String(labels.length - SHOWN)])}`
})
</script>

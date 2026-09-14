<template>
  <!--
    What somebody has left, per leave type.

    A number and a bar: the number is what they came for, and the bar is
    whether it is a lot — which a number on its own cannot say. `18 of 20` and
    `18 of 60` are the same number and not the same news.

    The arithmetic is the server's — allocated minus what approved applications
    used, in `oneapp/onehr/history.py` — and it is a summary rather than the
    figure a payroll run should trust. Extracted at its second caller: the
    person record and the employee's own home.
  -->
  <!--
    Capped rather than stretched. These are bars a reader compares with each
    other, and a row six hundred pixels wide puts the number so far from the
    label that the comparison is the thing that gets lost.
  -->
  <div v-if="balance.length" class="flex min-w-0 flex-1 flex-col gap-2 md:max-w-md">
    <p v-if="label" class="text-xs text-ink-muted">{{ label }}</p>
    <div class="flex flex-col gap-1.5" data-slot="person-balance">
      <div v-for="one in balance" :key="one.leave_type" class="flex items-center gap-3">
        <span class="w-32 shrink-0 truncate text-xs text-ink-secondary">
          {{ one.leave_type }}
        </span>
        <Progress class="min-w-0 flex-1" size="md" :value="leftShare(one)" />
        <span class="shrink-0 text-xs tabular-nums text-ink-secondary">
          {{ __('{0} of {1}', [String(one.left), String(one.allocated)]) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Progress } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** `[{leave_type, allocated, taken, left}]`. */
  balance: { type: Array, default: () => [] },
  /** The line above it. Empty where the block already has a heading. */
  label: { type: String, default: '' },
})

/** How full a bar is. Nothing allocated is nothing to draw, not an error. */
const leftShare = (one) => {
  const total = Number(one.allocated) || 0
  if (total <= 0) return 0
  return Math.round((Math.min(Number(one.left) || 0, total) / total) * 100)
}
</script>

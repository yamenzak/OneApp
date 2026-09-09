<template>
  <!--
    One planned call per row: what was published, what came, and the gap. Used
    twice on the same screen — once for calls nothing came to and once for the
    ones furthest from their published time — because the two are different
    findings and sorting them together buries the second.
  -->
  <div class="overflow-x-auto">
    <div class="min-w-[26rem]">
      <div
        class="grid grid-cols-[4rem_1fr_4.5rem_6rem_5rem] gap-2 pb-1 text-xs
               uppercase tracking-wide text-ink-gray-5"
      >
        <span>{{ __('Line') }}</span>
        <span>{{ __('Stop') }}</span>
        <span>{{ __('Due') }}</span>
        <span>{{ __('Came') }}</span>
        <span class="text-end">{{ __('Off by') }}</span>
      </div>
      <p v-if="!calls.length" class="py-3 text-sm text-ink-gray-5">
        {{ __('Nothing here, which is the good answer.') }}
      </p>
      <div
        v-for="one in calls"
        :key="`${one.trip_key}-${one.due}`"
        class="grid grid-cols-[4rem_1fr_4.5rem_6rem_5rem] items-baseline gap-2
               border-t border-outline-gray-1 py-1.5 text-sm"
      >
        <span class="truncate text-ink-gray-8">{{ one.line }}</span>
        <span class="truncate text-ink-gray-7">{{ one.stop }}</span>
        <span class="tabular-nums text-ink-gray-7">{{ clock(one.due) }}</span>
        <!--
          Said in words rather than left blank, and as a badge rather than as
          coloured text. An empty cell reads as data we do not have; this is
          data we do have, and what it says is that nothing came — which is a
          state, and states wear badges everywhere else in this product.
        -->
        <span v-if="one.seen" class="tabular-nums text-ink-gray-7">{{ clock(one.seen) }}</span>
        <Badge v-else theme="red" variant="subtle" :label="__('Nothing came')" />
        <span class="text-end font-medium tabular-nums text-ink-gray-8">
          {{ one.gap_s === null ? '—' : minutes(one.gap_s) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Badge } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** Planned calls, each with what came and how far off it was. */
  calls: { type: Array, default: () => [] },
})

/** A stamp as a clock reading. The date is the picker's; repeating it in every
 *  row is forty copies of something already on screen. */
function clock(stamp) {
  return String(stamp || '').slice(11, 16)
}

function minutes(seconds) {
  const value = Number(seconds) / 60
  const said = `${value > 0 ? '+' : ''}${value.toFixed(1)}`
  return __('{0} min', [said])
}
</script>

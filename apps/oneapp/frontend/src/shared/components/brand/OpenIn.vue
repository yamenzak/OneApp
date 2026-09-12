<template>
  <!--
    "Open in OneSheet", and the two beside it.

    One component because there are three of these and they are the same
    sentence: a table opens in OneSheet, a long field in OneDoc, a code field in
    OneCode. Three copies of one button is three places for the wording, the
    mark or the weight to drift, and they had already drifted once — the labels
    said "Open in a sheet" and "Open in the editor", which name a *kind* of
    thing rather than the product a person is about to be looking at.

    `One` is said quietly, as it is in the launcher and in the corner of every
    editor. It is four letters that are the same on all of them, and at full
    strength in a row of buttons it is noise repeated three times.
  -->
  <Button
    variant="ghost"
    size="sm"
    :data-slot="slotName"
    :tooltip="tooltip"
    :loading="loading"
    @click="emit('open')"
  >
    <template #prefix><BrandMark :name="brand" class="size-4 shrink-0" /></template>
    <!--
      `inline-flex` with a gap rather than two spans and a newline between them.
      Vue collapses the whitespace between sibling elements in a template, so
      the two-tone name read as "Open inOneCode" — the space was in the source
      and nowhere else.

      The verb is quieter than the name. What a person is choosing between on a
      row of these is the product, not the fact that all three of them open.
    -->
    <span class="inline-flex items-baseline gap-1 whitespace-nowrap">
      <span class="text-ink-muted">{{ __('Open in') }}</span>
      <SpaceName :brand="brand" />
    </span>
  </Button>
</template>

<script setup>
import { Button } from '@/ui'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** A key of `MARKS` — `onesheet`, `onedoc`, `onecode`. */
  brand: { type: String, required: true },
  /**
   * What this one opens, said in full. The button says only where it goes, so
   * the tooltip is where "the sheet these rows are priced in" belongs — and on
   * a row of three identical-looking buttons it is the only thing that
   * distinguishes them before the pointer arrives.
   */
  tooltip: { type: String, default: '' },
  /** The `data-slot` the suites point at. */
  slotName: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])
</script>

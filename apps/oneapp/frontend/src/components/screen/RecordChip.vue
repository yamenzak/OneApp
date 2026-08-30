<template>
  <!--
    One record, shown the way this product shows records: a face, a name, and
    the id underneath when the name is not already it.

    The same three things the title column shows, deliberately — a link *is* a
    record, and a person picking one out of a menu and reading one in a cell
    should not be looking at two different renderings of the same thing. Used by
    the list cell, by the link picker's rows, and by whatever view type comes
    next.
  -->
  <div class="flex min-w-0 items-center gap-2">
    <!--
      Always, image or not: Avatar falls back to initials, and that is what the
      title column already draws for a row with no picture. A face in one place
      and a bare word in the other reads as two kinds of thing.
    -->
    <Avatar
      :image="record.image"
      :label="String(record.label || record.value || '')"
      shape="square"
      :size="compact ? 'sm' : 'md'"
    />
    <div class="flex min-w-0 flex-col">
      <span class="truncate text-p-sm text-ink-gray-8">
        {{ record.label || record.value }}
      </span>
      <!-- The id, and anything the doctype calls searchable, quietly beneath —
           what a person quotes on the phone and never what they read first. -->
      <span v-if="detail" class="truncate text-p-xs text-ink-gray-5">{{ detail }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar } from '@/ui'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  /** A list cell is one line tall; a menu row has more room. */
  compact: { type: Boolean, default: false },
})

const detail = computed(() =>
  [props.record.id, props.record.description].filter(Boolean).join(' · '),
)
</script>

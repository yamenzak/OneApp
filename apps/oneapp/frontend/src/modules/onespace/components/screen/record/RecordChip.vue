<template>
  <!--
    One record, shown the way this product shows records: a face, a name, and
    the id underneath when the name is not already it.

    The same three things the title column shows, deliberately — a link *is* a
    record, and picking one out of a menu and reading one in a cell should not
    be two renderings of the same thing.
  -->
  <div class="flex min-w-0 items-center gap-2">
    <!--
      Image or not: Avatar falls back to initials, which is what the title
      column already draws. The one exception is a caller that has already drawn
      the face itself — see `avatar`.
    -->
    <Avatar
      v-if="avatar"
      :image="record.image"
      :label="plainText(record.label) || String(record.value || '')"
      shape="square"
      :size="compact ? 'sm' : 'md'"
    />
    <div class="flex min-w-0 flex-col">
      <div class="flex min-w-0 items-center gap-1.5">
        <span class="truncate text-sm text-ink-primary">
          {{ plainText(record.label) || record.value }}
        </span>
        <!-- Anything the caller wants said beside the name: a status badge in
             the breadcrumb, nothing in a list cell where the status has a
             column. -->
        <slot name="badge" />
      </div>
      <!-- The id, and anything the doctype calls searchable, quietly beneath —
           what a person quotes on the phone and never what they read first. -->
      <span v-if="detail" class="truncate text-xs text-ink-muted">{{ detail }}</span>
    </div>
  </div>
</template>

<script setup>
import { plainText } from '@/modules/onespace/lib/screen/format'
import { computed } from 'vue'
import { Avatar } from '@/ui'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  /** A list cell is one line tall; a menu row has more room. */
  compact: { type: Boolean, default: false },
  /**
   * Whether to draw the face. Off where the caller has already drawn it, and
   * bigger — a gallery card puts the record's image across the top.
   */
  avatar: { type: Boolean, default: true },
})

const detail = computed(() =>
  [props.record.id, props.record.description].filter(Boolean).join(' · '),
)
</script>

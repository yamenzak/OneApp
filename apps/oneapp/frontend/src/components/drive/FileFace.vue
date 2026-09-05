<!--
  What a file looks like: its icon or its thumbnail, its name, and its size.

  Its own component only because the row draws it twice — a folder is a
  `router-link` and a file is a `Button`, and the two branches are the same face
  in different clothes.
-->
<template>
  <!--
    One root, laying itself out. Both callers put this inside something whose
    own flex direction is not ours to assume — a `Button`'s content box is the
    library's, and the icon sat above the name for exactly as long as this was
    two loose spans trusting the parent.
  -->
  <span
    class="flex min-w-0 flex-1 items-center gap-3 text-left"
    :class="grid ? '!flex-col !items-stretch' : ''"
  >
  <span
    class="grid shrink-0 place-items-center overflow-hidden rounded-4 bg-surface-gray-2"
    :class="grid ? 'h-24 w-full' : 'size-8'"
  >
    <!-- An image is its own icon. Everything else gets the glyph for its kind,
         which is the whole reason the kind is a column. -->
    <img
      v-if="thumbnail"
      :src="thumbnail"
      :alt="file.file_name"
      class="h-full w-full object-cover"
      loading="lazy"
    />
    <Icon
      v-else
      :name="ICONS[file.custom_kind] || ICONS.Other"
      :class="grid ? 'size-8' : 'size-4'"
    />
  </span>

  <span class="min-w-0 flex-1">
    <span class="block truncate text-p-sm font-normal text-ink-gray-8">
      {{ file.file_name }}
    </span>
    <span class="block truncate text-p-xs font-normal text-ink-gray-5">
      {{ file.is_folder ? 'Folder' : size }}<template v-if="!grid"> · {{ when }}</template>
    </span>
  </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Icon, dayjsLocal } from '@/ui'

// One glyph per kind. The set is the server's `KINDS` and a value it does not
// know falls through to the same icon an unknown file gets.
const ICONS = {
  Folder: 'lucide-folder',
  Image: 'lucide-image',
  PDF: 'lucide-file-text',
  Video: 'lucide-video',
  Audio: 'lucide-music',
  Document: 'lucide-file',
  Sheet: 'lucide-table-2',
  Other: 'lucide-file-question',
}

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
})

// Only in the grid, and only for images: a list of forty rows fetching forty
// full-size objects to draw a 32px square is forty requests for nothing.
const thumbnail = computed(() =>
  props.grid && props.file.custom_kind === 'Image' ? props.file.file_url : '',
)

const size = computed(() => {
  const bytes = props.file.file_size || 0
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value < 10 && unit ? value.toFixed(1) : Math.round(value)} ${units[unit]}`
})

const when = computed(() =>
  props.file.modified ? dayjsLocal(props.file.modified).fromNow() : '',
)
</script>

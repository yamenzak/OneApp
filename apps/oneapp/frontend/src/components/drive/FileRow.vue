<!--
  One file, as a row or as a card.

  The same component draws both, because a list and a grid of the same files
  differ in layout and not in what a file *is* — two components would be two
  places to add a column to.
-->
<template>
  <!--
    A row is a link, not a button. A folder is a place with a URL — that is the
    whole reason the folder is in the query string — so the browser's own
    middle-click, copy-link and back button all work without a line of ours.
  -->
  <router-link
    v-if="file.is_folder"
    data-slot="drive-file"
    :data-kind="file.custom_kind || 'Other'"
    class="group w-full text-left"
    :class="
      grid
        ? 'flex flex-col gap-2 rounded-6 border border-outline-gray-1 p-3 hover:bg-surface-gray-1'
        : 'flex items-center gap-3 rounded-4 px-3 py-2 hover:bg-surface-gray-2'
    "
    :to="{ name: 'Drive', query: { place: 'home', folder: file.name } }"
  >
    <div
      class="grid shrink-0 place-items-center rounded-4 bg-surface-gray-2"
      :class="grid ? 'h-24 w-full' : 'size-8'"
    >
      <!-- An image is its own icon. Everything else gets the glyph for its
           kind, which is the whole reason the kind is a column. -->
      <img
        v-if="thumbnail"
        :src="thumbnail"
        :alt="file.file_name"
        class="h-full w-full rounded-4 object-cover"
        loading="lazy"
      />
      <Icon v-else :name="ICONS[file.custom_kind] || ICONS.Other" :class="grid ? 'size-8' : 'size-4'" />
    </div>

    <div class="min-w-0 flex-1">
      <p class="truncate text-p-sm text-ink-gray-8">{{ file.file_name }}</p>
      <p class="truncate text-p-xs text-ink-gray-5">
        Folder<span v-if="!grid"> · {{ when }}</span>
      </p>
    </div>

    <div v-if="!grid" class="flex shrink-0 items-center gap-3">
      <Avatar
        v-if="file.owner_person?.label"
        size="sm"
        :label="file.owner_person.label"
        :image="file.owner_person.image"
      />
      <span class="w-24 shrink-0 text-p-xs text-ink-gray-5">{{ when }}</span>
    </div>
  </router-link>

  <!-- A file is not a place, so it is a button: opening one is an action. -->
  <Button
    v-else
    data-slot="drive-file"
    :data-kind="file.custom_kind || 'Other'"
    variant="ghost"
    :label="file.file_name"
    class="!h-auto !w-full !justify-start !p-0"
    @click="emit('open', file)"
  >
    <span
      class="w-full text-left"
      :class="
        grid
          ? 'flex flex-col gap-2 rounded-6 border border-outline-gray-1 p-3'
          : 'flex items-center gap-3 rounded-4 px-3 py-2'
      "
    >
      <span
        class="grid shrink-0 place-items-center rounded-4 bg-surface-gray-2"
        :class="grid ? 'h-24 w-full' : 'size-8'"
      >
        <img
          v-if="thumbnail"
          :src="thumbnail"
          :alt="file.file_name"
          class="h-full w-full rounded-4 object-cover"
          loading="lazy"
        />
        <Icon
          v-else
          :name="ICONS[file.custom_kind] || ICONS.Other"
          :class="grid ? 'size-8' : 'size-4'"
        />
      </span>

      <span class="min-w-0 flex-1">
        <span class="block truncate text-p-sm text-ink-gray-8">{{ file.file_name }}</span>
        <span class="block truncate text-p-xs text-ink-gray-5">
          {{ size }}<template v-if="!grid"> · {{ when }}</template>
        </span>
      </span>

      <span v-if="!grid" class="flex shrink-0 items-center gap-3">
        <Avatar
          v-if="file.owner_person?.label"
          size="sm"
          :label="file.owner_person.label"
          :image="file.owner_person.image"
        />
        <span class="w-24 shrink-0 text-p-xs text-ink-gray-5">{{ when }}</span>
      </span>
    </span>
  </Button>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar, Button, Icon, dayjsLocal } from '@/ui'

// One glyph per kind. The set is the server's `KINDS` and a value it does not
// know falls through to the same icon an unknown file gets.
const ICONS = {
  Folder: 'lucide-folder',
  Image: 'lucide-image',
  PDF: 'lucide-file-text',
  Video: 'lucide-video',
  Audio: 'lucide-music',
  Document: 'lucide-file',
  Other: 'lucide-file-question',
}

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])

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

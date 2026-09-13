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
    class="flex min-w-0 flex-1 items-center gap-3 text-start"
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
      :name="iconForKind(file.custom_kind)"
      :class="grid ? 'size-8' : 'size-4'"
    />
  </span>

  <span class="min-w-0 flex-1">
    <span class="flex min-w-0 items-center gap-1.5 text-p-sm font-normal text-ink-primary">
      <span data-slot="file-name" class="truncate">{{ file.file_name }}</span>
      <!-- Where a model made this. Here rather than on the row, because this
           is the one component that draws a file's identity — the list, the
           grid, the picker and the previewer all come through it, so the mark
           reaches every one of them by being said once. See
           `components/AiMark.vue`. -->
      <AiMark v-if="file._ai" :mark="file._ai" />
    </span>
    <span v-if="meta" class="block truncate text-xs font-normal text-ink-muted">
      <!-- The separator belongs to the date, not to the line: a directory made
           out of a query has no date of its own, and a bare "Folder ·" reads
           as something that failed to load. -->
      <!-- In columns the size and the date have cells of their own, so the
           line under the name says the one thing they do not: what kind of
           thing this is. Saying it twice is how a column layout ends up
           wider than the window it is trying to make scannable. -->
      <template v-if="columns">{{
        file.is_folder ? labelForKind('Folder') : labelForKind(file.custom_kind)
      }}<!--
        The date, only where the column that would have carried it is not.

        `Last changed` hides below `md`, so a phone in columns mode was left
        with a kind and nothing else — the one screen where the line under the
        name is the only place a date can go. It comes back at exactly the
        width the column leaves.
      --><span v-if="when" class="md:hidden"> · {{ when }}</span></template>
      <template v-else>{{ file.is_folder ? labelForKind('Folder') : size
      }}<template v-if="!grid && when"> · {{ when }}</template></template>
    </span>
  </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@/ui'
import { iconForKind, labelForKind } from '@/modules/onestorage/lib/files'
import AiMark from '@/modules/onespace/components/AiMark.vue'
import { ago } from '@/shared/lib/runtime/format'
import { sizeText } from '@/shared/lib/files/size'

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
  /** The row is drawing size and date as columns, so this must not. */
  columns: { type: Boolean, default: false },
  /**
   * Whether to say what it is under the name.
   *
   * Off in the grid, where the card has a foot to put it in — beside the verbs
   * rather than above them, which is what stops that foot being a strip of
   * white with two icons adrift at one end of it.
   */
  meta: { type: Boolean, default: true },
})

// Only in the grid, and only for images: a list of forty rows fetching forty
// full-size objects to draw a 32px square is forty requests for nothing.
const thumbnail = computed(() =>
  props.grid && props.file.custom_kind === 'Image' ? props.file.file_url : '',
)

const size = computed(() => sizeText(props.file.file_size, { blank: '—' }))

const when = computed(() =>
  props.file.modified ? ago(props.file.modified) : '',
)
</script>

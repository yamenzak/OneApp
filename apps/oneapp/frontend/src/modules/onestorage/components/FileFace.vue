<!--
  What a file looks like: its mark or its thumbnail, its name, and one line of
  facts under it.

  Its own component only because the row draws it twice — a folder is a
  `router-link` and a file is a `Button`, and the two branches are the same face
  in different clothes.

  **The mark is artwork, not a glyph.** Derived from frappe/suite's Drive, which
  this is otherwise a rebuild of: their card is a thumbnail with a coloured
  format mark in its foot, and it reads as a file manager at a glance in a way a
  grid of grey lucide outlines does not. See `../art/README.md` for the licence
  and the renames. The glyphs stay where a glyph is right — a rail, a menu, a
  button — and come off the thing the reader is actually looking at.
-->
<template>
  <!--
    One root, laying itself out. Both callers put this inside something whose
    own flex direction is not ours to assume — a `Button`'s content box is the
    library's, and the icon sat above the name for exactly as long as this was
    two loose spans trusting the parent.

    `w-full` on a card for the same reason stated the other way round: `flex-1`
    is an instruction to a flex parent, and a `Button`'s content wrapper is not
    one, so the card's picture stopped thirty pixels short of its own border.
  -->
  <span
    class="flex min-w-0 flex-1 items-center gap-3 text-start"
    :class="asCard ? '!h-full !w-full !flex-col !items-stretch !gap-0' : ''"
  >
    <!--
      The picture, or the space where one would be.

      In a card this is the 65% of the height frappe/suite gives it, and the
      split is the whole reason their grid reads as a file manager: a
      thumbnail wants nearly all of the card, and the facts want one line
      under a rule. Ours was a 96px box with a name loose beneath it, which is
      a list row that had been made tall.

      A file with no thumbnail centres its mark at the size a thumbnail would
      have been rather than filling the space, so a wall of mixed cards has
      one baseline and not two.

      No radius of its own: the card clips, so a `rounded-t-*` here would be a
      fifth corner size drawn under a rounded edge that already hides it.

      **In a row the mark is bare.** The grey panel is the thumbnail's
      background and a row has no thumbnail, so all it did there was put a
      grey folder on a grey square — which is a black box at sixteen pixels,
      and was. These marks are drawn to sit on the page, which is how
      frappe/suite draws them in their own list.
    -->
    <span
      class="relative grid shrink-0 place-items-center overflow-hidden"
      :class="asCard
        ? 'h-[65%] w-full border-b border-outline-gray-1 bg-surface-gray-1'
        : 'size-5'"
    >
      <!--
        The mark is drawn first and stays drawn: it is what a card shows while
        the thumbnail is still arriving, and what it keeps if none ever does.
        The picture lies over it and fades in, so nothing moves and no card is
        ever empty. This is frappe/suite's arrangement and it is right.
      -->
      <img
        :src="mark"
        :alt="''"
        aria-hidden="true"
        :class="asCard ? 'size-10' : 'size-4'"
        draggable="false"
      />
      <img
        v-if="picture"
        :src="picture"
        :alt="file.file_name"
        loading="lazy"
        decoding="async"
        class="absolute inset-0 h-full w-full object-cover transition-opacity duration-150"
        :class="loaded ? 'opacity-100' : 'opacity-0'"
        draggable="false"
        @load="loaded = true"
        @error="picture = ''"
      />
    </span>

    <span
      class="min-w-0 flex-1"
      :class="asCard ? 'flex h-[35%] flex-col justify-center gap-0.5 p-2' : ''"
    >
      <span class="flex min-w-0 items-center gap-1.5 text-p-sm font-normal text-ink-primary">
        <span data-slot="file-name" class="truncate">{{ file.file_name }}</span>
        <!-- Where a model made this. Here rather than on the row, because this
             is the one component that draws a file's identity — the list, the
             grid, the picker and the previewer all come through it, so the mark
             reaches every one of them by being said once. See
             `components/AiMark.vue`. -->
        <AiMark v-if="file._ai" :mark="file._ai" />
      </span>
      <span
        v-if="meta && !(file.is_folder && (columns || grid)) && !(kindKnown && columns)"
        class="flex min-w-0 items-center gap-1 text-xs font-normal text-ink-muted"
      >
        <!--
          The format mark again, small, beside the words — but only on a card
          whose picture has covered the big one up. Without it a photograph's
          card says "Image · 413 B" under a picture and nothing says which
          format; with it on every card it is the same mark twice, six
          millimetres apart.
        -->
        <img
          v-if="asCard && loaded"
          :src="mark"
          :alt="''"
          aria-hidden="true"
          class="size-3.5 shrink-0"
          draggable="false"
        />
        <!-- The separator belongs to the date, not to the line: a directory made
             out of a query has no date of its own, and a bare "Folder ·" reads
             as something that failed to load. -->
        <!-- In columns the size and the date have cells of their own, so the
             line under the name says the one thing they do not: what kind of
             thing this is. Saying it twice is how a column layout ends up
             wider than the window it is trying to make scannable. -->
        <!-- And a folder has no line at all, in columns or in the grid. Its
             mark is an amber folder and it sits under a heading that says
             FOLDERS, so "Folder" under the name was the third telling, on
             every row, in a list that is mostly folders. It read as a
             subtitle, which is what a subtitle saying nothing looks like. The
             date goes with it in columns, which costs a phone the one place
             it could have read a folder's date: the least interesting fact
             here. -->
        <span class="truncate">
          <template v-if="columns">{{ labelForKind(file.custom_kind) }}<!--
            The date, only where the column that would have carried it is not.

            `Last changed` hides below `md`, so a phone in columns mode was left
            with a kind and nothing else — the one screen where the line under the
            name is the only place a date can go. It comes back at exactly the
            width the column leaves.
          --><span v-if="when" class="md:hidden"> · {{ when }}</span></template>
          <template v-else>{{ file.is_folder ? '' : size
          }}<template v-if="!grid && when"> · {{ when }}</template></template>
        </span>
      </span>
    </span>
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { artFor, thumbnailUrl } from '@/modules/onestorage/lib/art'
import { labelForKind } from '@/modules/onestorage/lib/files'
import AiMark from '@/modules/oneai/components/AiMark.vue'
import { ago } from '@/shared/lib/runtime/format'
import { sizeText } from '@/shared/lib/files/size'

const props = defineProps({
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
  /** The row is drawing size and date as columns, so this must not. */
  columns: { type: Boolean, default: false },
  /** Whether this is a folder somebody else owns, which has its own mark. */
  shared: { type: Boolean, default: false },
  /**
   * Whether the *list* is already one kind, so naming it is naming the room.
   *
   * Every row in OneWriter is a document and every row in OneWorkbook is a
   * sheet — the window's title says so and its mark says so — and "Doc" under
   * fifty names is the third telling, which is the same thing "Folder" under
   * every folder was. In the grid the line still carries the size, which is a
   * fact about the file rather than about the room.
   */
  kindKnown: { type: Boolean, default: false },
  /**
   * Whether to say what it is under the name.
   *
   * On in a card now, where it used to be off: the facts moved off the row's
   * foot and back under the name, which is where frappe/suite keeps them and
   * where they belong — a card's foot holding two verbs and a sentence was
   * the reason the name had no width.
   */
  meta: { type: Boolean, default: true },
})

const mark = computed(() => artFor(props.file, { shared: props.shared }))

/**
 * The thumbnail, in the grid only.
 *
 * A list of forty rows asking for forty thumbnails to fill a 32px square is
 * forty requests for something nobody can see. In a card it is the point.
 *
 * A `ref` rather than a computed because it has to be able to give up: a
 * thumbnail that fails — an object that has gone, a format the server could
 * not decode — clears itself on `error` and the mark underneath is already
 * there. Watched so that a card recycled onto a different file asks again.
 */
const picture = ref('')
const loaded = ref(false)
watch(
  () => [props.grid, props.file?.name],
  () => {
    loaded.value = false
    picture.value = props.grid ? thumbnailUrl(props.file) : ''
  },
  { immediate: true },
)

/**
 * Whether this draws as a card with a picture on it, or as a line with a mark.
 *
 * A folder has no thumbnail and never will: there is nothing to show but the
 * same folder mark blown up, which is a lot of card spent saying "folder"
 * twice. In the grid it keeps the row's shape — mark beside name — so a place
 * reads as a place and the cards are the things you can actually look at.
 * Which is what every file manager does, and why their folder rows are short.
 */
const asCard = computed(() => props.grid && !props.file.is_folder)

const size = computed(() => sizeText(props.file.file_size, { blank: '—' }))

const when = computed(() =>
  props.file.modified ? ago(props.file.modified) : '',
)
</script>

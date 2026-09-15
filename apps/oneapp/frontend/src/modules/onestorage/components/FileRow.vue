<!--
  One file, as a row or as a card. The same component draws both, because a list
  and a grid of the same files differ in layout and not in what a file *is*.

  The row is a container and not itself the control: opening a file and hearting
  it are different actions on the same line, and a button inside a button is
  neither valid nor reachable by a keyboard. On a *row* those controls are
  always drawn rather than revealed on hover — a phone has no hover, and a row
  has a column to keep them in either way. A *card* has no such column: its
  whole area is the picture and the name, so there the controls lie over the
  corners and appear on hover, which is frappe/suite's arrangement and every
  other file manager's.
-->
<template>
  <!--
    In the grid a folder is a chip and a file is a card.

    A folder has no thumbnail and never will, so a card of one is 96 pixels
    spent drawing the glyph twice. It keeps the row's shape and sits in a track
    beside its neighbours, which is how a file manager shows a dozen folders
    without a dozen rows.

    It fits a 12rem track because the verbs came off it: the heart and the
    download were taking the width the *name* needed, and the name is the one
    thing on a folder worth reading. Both are on the menu now, which is where
    a card's actions belong and where this row already had one.
  -->
  <div
    data-slot="drive-file"
    :data-kind="kind"
    :data-selected="selected ? 'true' : undefined"
    :draggable="movable"
    :class="[
      card
        ? 'group relative h-40 overflow-hidden rounded-6 border border-outline-gray-1 md:h-[172px]'
        : grid
          ? 'group relative flex items-center gap-2 overflow-hidden rounded-6 border border-outline-gray-1 p-2'
          : 'flex items-center gap-2 rounded-4 pe-2',
      rowState({ selected, drop: over, lifted }),
    ]"
    @contextmenu="emit('menu', menu)"
    @dragstart="onDragStart"
    @dragend="lifted = false"
    @dragover="onDragOver"
    @dragleave="over = false"
    @drop="onDrop"
  >
    <!-- Selection is opt-in per surface: the picker offers one file, and a
         checkbox there would do nothing. -->
    <!-- `aria-label` and not `label`: frappe-ui's Checkbox renders a label as
         visible text, and forty rows captioned "Select Perspective.jpg" is a
         column of instructions. -->
    <!--
      In the grid it sits *on* the thumbnail rather than above it. A tick with
      a line of its own cost every card a row of white for one control, and
      made a wall of cards read as a wall of checkboxes. Over the corner is
      where every file manager puts it and where a card has room to spare.
    -->
    <Checkbox
      v-if="selectable && !remote"
      :model-value="selected"
      :aria-label="__('Select {0}', [file.file_name])"
      :class="[
        'shrink-0',
        grid ? 'absolute start-2 top-2 z-10' : 'ms-2.5',
        grid && !selected ? 'md:hidden md:group-hover:block' : '',
      ]"
      @update:model-value="emit('select', file)"
    />

    <!--
      A card says it is a favourite with a mark in the corner the tick is not
      using, and gives the corner up the moment the tick needs it. Not a
      control: the heart is on the menu, and a badge you can press is a badge
      somebody presses by accident while choosing files.

      It is the one thing the card can say that the row says with a filled
      heart in its own column — and Favourites is the place where every row
      would carry it, so there it says nothing and is left off.
    -->
    <Icon
      v-if="card && file.liked && place !== 'favourites'"
      name="lucide-heart"
      class="absolute start-2 top-2 z-10 size-4 fill-current text-ink-red-3"
      :class="selectable ? 'md:group-hover:hidden' : ''"
      aria-hidden="true"
    />

    <!--
      Anything with an address is a link; everything else is a button.

      A folder always was: it is a place, so middle-click, copy-link and the
      back button work without a line of ours. What changed is that a sheet, a
      document and a text file are places too now — `routeFor` gives each one a
      URL — and while they were buttons the only way to keep a quotation open
      while pricing it was a window manager we would have had to write. A
      cmd-click is that window manager, and every browser already ships it.

      A `.zip` is still not a place. Opening one is an action, and it stays a
      button.
    -->
    <!--
      `inline` is the host saying it will open this one itself.

      The link stays a link — that is what makes cmd-click open a tab, and a
      file manager where a modifier does nothing is a file manager somebody
      fights. What changes is the plain click: the Drive opens a sheet in the
      pane beside the list rather than walking away from the list, so it takes
      the click and the anchor keeps every other way of using it.
    -->
    <router-link
      v-if="(file.is_folder && folderLink) || link"
      data-slot="drive-open"
      class="flex min-w-0 flex-1 rounded-4"
      :class="card ? 'h-full' : grid ? 'ps-1' : 'px-2 py-2'"
      :to="file.is_folder
        ? { name: 'Drive', query: { place, folder: file.name } }
        : link"
      @click.capture="onOpen"
    >
      <FileFace :file="file" :grid="grid" :columns="columns" :shared="shared" :kind-known="kindKnown" />
    </router-link>

    <!--
      A card that opens nothing a URL can name — a `.zip`, a photograph — is a
      tile, and a tile is not a `Button`.

      `RecordCard` settled this for the gallery and the reason is the same
      here: frappe-ui's Button wraps its slot in a `truncate` span, which is an
      inline box that will not stretch, so the card's picture stopped thirty
      pixels short of its own border and nothing about the class list could
      reach in and say otherwise. It also brings a height, a padding and a
      label layout to a thing that is none of those.

      The tile is the click surface; every control on it — the tick, the menu —
      is its own button over the top and stops the event.
    -->
    <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
    <button
      v-else-if="card"
      data-slot="drive-open"
      type="button"
      class="flex h-full w-full min-w-0 flex-1 rounded-6 text-start"
      :aria-label="file.file_name"
      @click="emit('open', file)"
    >
      <FileFace :file="file" :grid="grid" :columns="columns" :shared="shared" :kind-known="kindKnown" />
    </button>

    <Button
      v-else
      data-slot="drive-open"
      variant="ghost"
      :label="file.file_name"
      class="!h-auto min-w-0 flex-1 !justify-start"
      :class="grid ? '!ps-1 !pe-0 !py-0' : '!px-2 !py-2'"
      @click="emit('open', file)"
    >
      <FileFace :file="file" :grid="grid" :columns="columns" :shared="shared" :kind-known="kindKnown" />
    </Button>

    <!--
      In the grid the controls lie over the tile's top corners, which is where
      frappe/suite puts them and where every file manager has put them: a
      tile's own space is its picture and its name, and a strip reserved for
      two controls is a strip taken off both.

      A folder chip needs this more than a card does, not less. It is 170px
      wide, and a tick and a menu inline were taking sixty of them — which is
      why `Attachments` read as `Attach…`. `hidden` and not `invisible`
      because an invisible control still holds its box, so hiding it that way
      would have bought the name nothing at all.

      not-a-tooltip: `group-hover` here reveals a tile's real controls — a
      tick and a menu — rather than drawing a hover card. There is nothing for
      frappe-ui's Tooltip to be: the things being revealed are a Checkbox and a
      Button, each of which carries its own label and, in the Button's case,
      its own tooltip once it is visible.

      Below the shell's own breakpoint they are simply drawn, because a touch
      screen has no hover and a control that needs one is a control nobody can
      reach. `md:` and not `sm:` for the reason every layout branch in this
      product uses it — `breakpoint.js` picked the number and the shell
      switches there.
    -->
    <div
      :class="[
        'flex items-center gap-1',
        grid ? 'absolute end-2 top-2 z-10' : 'shrink-0',
        grid && !selected ? 'md:hidden md:group-hover:flex' : '',
      ]"
    >
      <!-- The heart is the whole of Favourites: `_liked_by` on the row, which
           the framework keeps on every doctype. -->
      <!--
        Not when the list is squeezed. `dense` means something else is sharing
        this width — the Drive's pane, open on a file — and at that width two
        icon buttons and a tick are the whole row: the name, which is the one
        thing a file list is for, had nothing left and drew as nothing at all.
        Both verbs are on the menu, which is where a narrow row keeps them.
      -->
      <Button
        v-if="actions && !remote && !grid && !dense"
        icon="lucide-heart"
        variant="ghost"
        :class="file.liked ? 'text-ink-red-3' : 'text-ink-gray-4'"
        :label="
          file.liked
            ? __('Remove {0} from favourites', [file.file_name])
            : __('Add {0} to favourites', [file.file_name])
        "
        :tooltip="file.liked ? __('Remove from favourites') : __('Add to favourites')"
        @click="emit('favourite', file)"
      />

      <!--
        Download, beside the heart and always drawn.

        Every file manager anybody uses puts this on the row. It was reachable
        only from the pane, which means opening a file to save it — and on a
        list of forty that is forty clicks nobody should make. Drawn rather
        than revealed for the reason the heart is: a phone has no hover.
      -->
      <Button
        v-if="actions && !remote && !file.is_folder && !grid && !dense"
        icon="lucide-download"
        variant="ghost"
        class="text-ink-gray-4"
        :label="__('Download {0}', [file.file_name])"
        :tooltip="__('Download')"
        @click="emit('download', file)"
      />
      <!-- A folder has nothing to download and still has to hold the place
           open, or every cell on its row sits a button left of the same cell
           on the row above it. -->
      <span v-else-if="actions && !remote && !grid && !dense" class="size-7 shrink-0" />

      <!--
        The columns, where the caller asked for them.

        Widths are fixed and the name is what flexes, because a column that
        resizes with its content is a column that moves every time somebody
        opens a folder — the thing a header row exists to stop. Each drops at
        its own width rather than all together: a phone keeps the name and the
        date, a laptop gets the owner back.
      -->
      <template v-if="columns && !grid">
        <!-- Only where there is more than one of them. A workspace one person
             uses answers "Administrator" on every row of every folder for
             ever, which is 144 pixels of the name's width spent on a fact
             nobody can act on. `ownered` is the list's own answer and is
             passed in rather than worked out here, because a column that
             appeared and vanished per row would be a table with ragged
             cells. -->
        <span v-if="ownered" class="hidden w-36 shrink-0 items-center gap-1.5 lg:flex">
          <Avatar
            v-if="file.owner_person?.label"
            size="sm"
            :label="file.owner_person.label"
            :image="file.owner_person.image"
          />
          <span class="truncate text-xs text-ink-muted">
            {{ file.owner_person?.label || '—' }}
          </span>
        </span>
        <span class="hidden w-28 shrink-0 text-xs text-ink-muted md:block">
          {{ when }}
        </span>
        <!-- A size is a quantity, so it lines up on its last digit. A folder
             has none, and an em dash is the column saying so rather than
             leaving a hole. -->
        <span class="hidden w-20 shrink-0 text-end text-xs text-ink-muted md:block">
          {{ file.is_folder ? '—' : sized }}
        </span>
      </template>

      <!-- Who and when, on a screen with room for them. On a phone they are the
           first two things to go. -->
      <template v-else-if="!grid">
        <Avatar
          v-if="file.owner_person?.label && !dense"
          class="hidden md:flex"
          size="sm"
          :label="file.owner_person.label"
          :image="file.owner_person.image"
        />
        <!-- The same words the face already says under the name — "Folder ·
             9 days ago" — so in a narrow list it is the column to lose, not
             the name. -->
        <span
          v-if="!dense"
          class="hidden w-24 shrink-0 text-p-xs text-ink-muted md:block"
        >
          {{ when }}
        </span>
      </template>

      <!-- The same menu a record's row has, in the same place, revealed the
           same way — `shared/components/RowMenu.vue`. -->
      <RowMenu
        v-if="menu.length"
        :items="menu"
        :label="__('What to do with {0}', [file.file_name])"
        :always="grid"
        
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Avatar, Button, Checkbox, Icon } from '@/ui'
import RowMenu from '@/shared/components/RowMenu.vue'
import FileFace from '@/modules/onestorage/components/FileFace.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'
import { sizeText } from '@/shared/lib/files/size'
import { rowState } from '@/shared/lib/rowstate'

const props = defineProps({
  /**
   * Whether the Owner column is drawn at all — the list says so, because the
   * answer is a fact about the whole page and not about this row.
   */
  ownered: { type: Boolean, default: true },
  /** Whether the list is already one kind — `FileFace`. */
  kindKnown: { type: Boolean, default: false },
  file: { type: Object, required: true },
  grid: { type: Boolean, default: false },
  /**
   * Lay the metadata out as fixed columns under a header the caller draws.
   *
   * Off by default, because the other two readings of this row are narrow: a
   * picker in a dialog and a record's Files tab beside a form have no width
   * for an owner column and no header to line one up with.
   */
  columns: { type: Boolean, default: false },
  // Off in the picker, which offers one file and has nothing to do in bulk.
  /**
   * Which place this row is in, so walking into a folder stays in it.
   *
   * It was `'home'` outright, which was true while every folder was a real
   * `File` under the drive. The Records place is a tree — `Quotation` then
   * `QTN-0001` — and a row there that linked to `place=home` would walk out of
   * the tree on the first click.
   */
  place: { type: String, default: 'home' },
  /**
   * Whether a folder row is a link into the Drive.
   *
   * True in the Drive, where a folder *is* somewhere to go. False where the
   * caller keeps its own idea of which folder it is showing — a record's Files
   * tab walks its room without leaving the record, and a row that navigated to
   * the Drive would take the record away to show you something the tab was
   * about to show you anyway.
   */
  folderLink: { type: Boolean, default: true },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
  // Off in the picker too: a rename control behind an Attach field is a control
  // in the wrong place.
  actions: { type: Boolean, default: false },
  /**
   * Where clicking this file goes, when it goes anywhere: a route location
   * from `routeFor`, or null for a file that is looked at rather than opened.
   *
   * Passed rather than computed here because the caller is the one that knows
   * what to come back to — a record's Files tab sends the record along so the
   * editor's trail leads home.
   */
  link: { type: Object, default: null },
  // What the bin offers instead, because everything else there is a no-op.
  trashed: { type: Boolean, default: false },
  canWrite: { type: Boolean, default: true },
  // Dragging is the Drive's alone: in the picker there is nowhere to drag to.
  movable: { type: Boolean, default: false },
  /**
   * The kinds this host opens itself rather than navigating to.
   *
   * The Drive passes Sheet and Doc: those open in the pane beside the list.
   * Everywhere else this is empty and a link is a link.
   */
  inline: { type: Array, default: () => [] },
  /**
   * The list is sharing its width with something — the Drive's pane, open on a
   * file. A viewport breakpoint cannot see that: the window is still wide and
   * only this column is narrow, so who-and-when goes on a word from the host
   * rather than on `sm:`. The name is what a list is for; the avatar is not.
   */
  dense: { type: Boolean, default: false },
  /**
   * Whether this folder is somebody else's, which gives it a different mark.
   *
   * The Shared place is the one list where every row is, so the caller says it
   * for the whole list rather than this working it out per row from an owner
   * it would have to compare against the session.
   */
  shared: { type: Boolean, default: false },
})

/**
 * A plain click on a kind the host claims, handed to the host.
 *
 * Every modifier is left alone — cmd, ctrl, shift, middle-click and the
 * context menu all belong to the anchor, and taking them would be taking the
 * only ways to open a second one.
 *
 * On the capture phase, which is the whole reason this works. `RouterLink`
 * binds its own click handler inside its render, so a plain `@click` here is a
 * fallthrough listener that runs *after* it — the navigation has already been
 * decided by the time `preventDefault` is called, and the page changes anyway.
 * A capture listener on the same element runs before every bubble one.
 */
function onOpen(event) {
  if (props.file.is_folder) return
  if (!props.inline.includes(props.file.custom_kind)) return
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return
  event.preventDefault()
  emit('open', props.file)
}

const emit = defineEmits([
  'open', 'select', 'favourite', 'share', 'rename', 'move', 'trash', 'restore',
  'destroy', 'menu', 'move-into', 'copy', 'download',
])

/**
 * A file on a mounted host, which is not a row here at all.
 *
 * Nothing that writes is offered on one: there is no `File` to rename, no
 * `_liked_by` to heart and no `DocShare` to hang a share on. The server
 * refuses all three with a sentence rather than a stack trace — see
 * `remote.deny` — and this is the half that stops anybody reaching them.
 */
const remote = computed(() => !!props.file.remote)

const menu = computed(() => {
  if (!props.actions) return []
  if (remote.value) {
    // One thing, and it is the seam: bringing the file across is what makes
    // every other item on this menu possible.
    return props.file.is_folder
      ? []
      : [{
        label: __('Copy into the Drive'),
        icon: 'lucide-download',
        onClick: () => emit('copy', props.file),
      }]
  }
  if (props.trashed) {
    return [
      { label: __('Put it back'), icon: 'lucide-rotate-ccw', onClick: () => emit('restore', props.file) },
      { label: __('Delete for ever'), icon: 'lucide-trash-2', theme: 'red', onClick: () => emit('destroy', props.file) },
    ]
  }
  const items = [{
    label: props.file.liked ? __('Remove from favourites') : __('Add to favourites'),
    icon: 'lucide-heart',
    onClick: () => emit('favourite', props.file),
  }]
  // The commonest thing anybody does to a file, and it was on no menu here at
  // all: the pane had a download button and the row it was opened from did not.
  if (!props.file.is_folder) {
    items.push({
      label: __('Download'),
      icon: 'lucide-download',
      onClick: () => emit('download', props.file),
    })
  }
  items.push({ label: __('Share'), icon: 'lucide-user-plus', onClick: () => emit('share', props.file) })
  if (props.canWrite) {
    items.push(
      { label: __('Rename'), icon: 'lucide-pencil', onClick: () => emit('rename', props.file) },
      { label: __('Move to a folder'), icon: 'lucide-folder-input', onClick: () => emit('move', props.file) },
      { label: __('Move to the bin'), icon: 'lucide-trash-2', theme: 'red', onClick: () => emit('trash', props.file) },
    )
  }
  return items
})

/**
 * Whether this row is a card with a picture on it.
 *
 * A folder in the grid is not: it keeps the row's shape, so the tick and the
 * menu stay inline rather than floating over a thumbnail that does not exist.
 * `FileFace` decides the same thing from the same two facts — kept in step by
 * being the same sentence, which is the most this is worth.
 */
/**
 * What kind of thing this row is, for anything reading the row rather than the
 * face — `data-kind`, and the specs that narrow a list to the files in it.
 *
 * `is_folder` first, which is how `FileFace` draws the line under the name. A
 * folder made before the kind column existed has no `custom_kind` of its own —
 * `Home/Attachments` is one on every site — so the stored value alone called it
 * Other while the face called it Folder. One row saying two things, and the one
 * a test can read was the wrong one.
 */
const kind = computed(() => (
  props.file.is_folder ? 'Folder' : (props.file.custom_kind || 'Other')
))

const card = computed(() => props.grid && !props.file.is_folder)

const sized = computed(() => sizeText(props.file.file_size, { blank: '—' }))

const when = computed(() =>
  props.file.modified ? ago(props.file.modified) : '',
)

// --- dragging a row onto a folder -------------------------------------------

// Our own MIME type, and not `text/plain`: a row dragged into a text field
// would otherwise paste a row id, and a file dragged in from the desktop would
// look to us like one of ours.
const MOVING = 'application/x-onespace-file'

const lifted = ref(false)
const over = ref(false)

function onDragStart(event) {
  if (!props.movable || remote.value) return
  lifted.value = true
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData(MOVING, props.file.name)
}

function onDragOver(event) {
  // Only a folder is a destination, and only for one of ours. A file dragged
  // from the desktop falls through to the page's own drop zone, which uploads
  // it.
  // A mount is read-only through the Drive, so it is not a drop target either.
  if (remote.value) return
  if (!props.file.is_folder || !event.dataTransfer.types.includes(MOVING)) return
  event.preventDefault()
  event.stopPropagation()
  event.dataTransfer.dropEffect = 'move'
  over.value = true
}

function onDrop(event) {
  over.value = false
  if (!props.file.is_folder) return
  const moving = event.dataTransfer.getData(MOVING)
  if (!moving || moving === props.file.name) return
  event.preventDefault()
  event.stopPropagation()
  emit('move-into', props.file, [moving])
}

</script>

<template>
  <!--
    Every document and sheet somebody has open, each in a window.

    They opened in the Drive's pane, which was right while the Drive was a
    page: 45% of a laptop is a reasonable spreadsheet. OneCloud is a window
    now, and a pane inside one is four columns and a scrollbar — so a file you
    work in gets a window and the pane keeps what it is for, which is looking
    at things.

    `lib/editing.js` holds the list and the argument, including why this is not
    an exception to stage 5's rule about what a window may hold.

    **The editors are the same components the pane used**, with the same
    `hosted` prop, because a document open in a window and a document open in a
    pane are the same document — what differs is the chrome around it, and the
    chrome is the frame's business.
  -->
  <DeskWindow
    v-for="one in openFiles"
    :key="one.name"
    :id="EDITOR + one.name"
    :memory="CORNER"
    :title="one.label"
    :label="one.label"
    :tint="colourOf(brandFor(one.editor))"
    :width="1100"
    :height="720"
    :min-width="520"
    :min-height="360"
    @close="closeFile(one.name)"
  >
    <!--
      The app's mark, and the file's name beside it.

      The mark and not the file-kind art. Every other window in the product
      wears the mark of the thing it is — OneCloud's bar and its dock tile draw
      the same cloud — and this window's own tile draws OneWriter's pen, so
      anything else here would be two drawings for one window. It is also the
      logo the editor's bar used to carry before that bar was folded into this
      one, which is where it went.
    -->
    <template #title>
      <BrandMark :name="brandFor(one.editor)" class="size-5 shrink-0" />
      <p class="truncate text-base font-medium text-ink-primary">{{ one.label }}</p>
    </template>

    <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
      <!--
        `:key` on the name for the reason `Doc.vue` gives at length: an editor
        is bound to a Y.Doc that belongs to one file and to a room joined for
        it, so re-pointing one would leave both behind and type the second
        document into the first one's room. A window per file makes that
        impossible rather than merely avoided, which is the better shape.
      -->
      <SheetEditor
        v-if="one.editor === 'sheet'"
        :key="one.name"
        :id="one.name"
        :host-menu="[]"
        hosted
        @close="closeFile(one.name)"
      />
      <Doc v-else :key="one.name" :name="one.name" hosted />
    </div>
  </DeskWindow>
</template>

<script setup>
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import Doc from '@/modules/onedoc/pages/Doc.vue'
import SheetEditor from '@/modules/onesheet/components/editor/index.vue'
import { CORNER, EDITOR, brandFor, closeFile, openFiles } from '@/modules/onestorage/lib/editing'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import { colourOf } from '@/shared/lib/brand/naming'
</script>

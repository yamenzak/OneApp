<template>
  <!--
    An open record. Beside the list on a desktop, over it on a phone.

    Frappe CRM's shape, and it earns its place for a reason a dialog cannot: a
    record is a place you work *while* looking at the list, and a modal takes
    the list away and the page out of the accessibility tree with it.

    On a phone there is no room to keep both, so it is a page. And on a screen
    that declares a showcase it is a page on a desktop too — a hero photograph
    in a 480-pixel column is a thumbnail with a headline over it.
  -->
  <!--
    Above the list, and above what the list draws over itself. `z-40` and not
    `z-20`: the grid's "there is more to the right" fade is `z-30`, and at 20 it
    showed through the opaque pane as a grey smear down its right edge.
  -->
  <div
    v-if="phone"
    data-slot="record-pane"
    class="fixed inset-x-0 bottom-0 top-0 z-40 flex flex-col bg-surface-base"
  >
    <slot name="body" :phone="true" />
  </div>

  <!--
    A page on a desktop: the content area, whole. Not the phone's fixed overlay
    — the rail and the trail above are still the way back.

    The list is still mounted behind this; the host hides it rather than tearing
    it down, so closing the record comes back to the rows and the scroll
    position that were there.
  -->
  <div
    v-else-if="page"
    data-slot="record-pane"
    class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-6 bg-surface-base"
  >
    <slot name="body" :phone="false" />
  </div>

  <template v-else>
    <!--
      The handle, and everything about resizing with it: the floor, the ceiling,
      the keyboard, the width remembered per browser. All of that used to be
      written out here, which is why the sidebar never became resizable.
    -->
    <Resizer
      v-model="width"
      :min="min"
      :default-size="DEFAULT"
      :max-share="maxShare"
      side="left"
      :label="__('the record')"
      remember="onespace.record-pane"
      slot-name="record-resizer"
    />

    <!-- Its own panel, beside the list's. Both sit on the shell's ground with
         a gutter between them, which is what says they are two things you are
         looking at rather than one thing with a rule down it. -->
    <div
      data-slot="record-pane"
      class="flex shrink-0 flex-col overflow-hidden rounded-6 bg-surface-base"
      :style="{ width: `${width}px` }"
    >
      <slot name="body" :phone="false" />
    </div>
  </template>
</template>

<script setup>
import Resizer from '../../Resizer.vue'
import { DEFAULT, MIN, useRecordPane } from '@/lib/screen/pane'
import { __ } from '@/lib/runtime/translate'
import { useIsMobile } from '@/lib/shell/breakpoint'

defineProps({
  /**
   * How wide the pane may get, as a share of the window.
   *
   * Not much more than a third. The other side is a table, and a table stops
   * being one column at a time: at .6 on a 1280px window the list was down to
   * Description alone, with Status, Priority and everything after it gone —
   * which is not a narrower list, it is a different screen.
   */
  maxShare: { type: Number, default: 0.45 },
  /**
   * The narrowest this pane may be, which is also the narrowest it opens at.
   *
   * A prop rather than the module's `MIN` alone, because what fits depends on
   * what is in it: a record's fields read at 360, and a spreadsheet at 360 is
   * four columns. The Resizer clamps *up* to this, so a remembered width from
   * a narrower use is widened rather than obeyed — and dragging wider still
   * works and is still remembered.
   */
  min: { type: Number, default: MIN },
  /**
   * Whether the record takes the whole content area rather than a column of it.
   * The screen's decision, not this component's — the host passes what the
   * manifest said.
   */
  page: { type: Boolean, default: false },
})

// Asked here rather than passed in: how a surface renders at a width is the
// surface's own business, and the screen host is not allowed to ask the
// viewport anything.
const phone = useIsMobile()

// Shared, because the bar above draws a block exactly this wide to carry the
// pane's own trail — see `lib/screen/pane.js`.
const { width } = useRecordPane()
</script>

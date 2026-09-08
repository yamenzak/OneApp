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
      :min="MIN"
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
import { ref } from 'vue'
import Resizer from '../../Resizer.vue'
import { __ } from '@/lib/runtime/translate'
import { useIsMobile } from '@/lib/shell/breakpoint'

defineProps({
  /** How wide the pane may get, as a share of the window. */
  maxShare: { type: Number, default: 0.6 },
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

// Narrow enough that a form is still readable, and no narrower: below this the
// labels wrap and the pane is a column of hyphens.
const MIN = 360
const DEFAULT = 480

const width = ref(DEFAULT)
</script>

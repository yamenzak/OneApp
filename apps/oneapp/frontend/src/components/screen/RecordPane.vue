<template>
  <!--
    An open record. Beside the list on a desktop, over it on a phone.

    Frappe CRM's shape, and it earns its place for a reason a dialog cannot:
    a record is a place you work *while* looking at the list — mark this one
    done, glance at the next, come back — and a modal takes the list away and
    the page out of the accessibility tree with it. A pane keeps both.

    On a phone there is no room to keep both, so it is a page: full width, its
    own header, and the way back where the way back goes.

    And on a screen that declares a showcase, it is a page on a desktop too —
    see `page`. A hero photograph in a 480-pixel column is a thumbnail with a
    headline over it, which is the opposite of what a showcase is for.
  -->
  <!--
    Above the list, and above what the list draws over itself. `z-40` and not
    `z-20`: the grid's "there is more to the right" fade is `z-30`, and at 20
    it showed through the page as a grey smear down its right edge — the pane
    is opaque, so it read as a rendering fault rather than as a layer.
  -->
  <div
    v-if="phone"
    data-slot="record-pane"
    class="fixed inset-x-0 bottom-0 top-0 z-40 flex flex-col bg-surface-base"
  >
    <slot name="body" :phone="true" />
  </div>

  <!--
    A page on a desktop: the content area, whole. Not the phone's fixed
    overlay — the rail and the trail above are still the way back, and covering
    them would make the X the only way out of a record you arrived at by
    clicking a row.

    The list is still mounted behind this; the host hides it rather than
    tearing it down, so closing the record comes back to the rows and the
    scroll position that were there.
  -->
  <div
    v-else-if="page"
    data-slot="record-pane"
    class="flex min-h-0 flex-1 flex-col overflow-hidden"
  >
    <slot name="body" :phone="false" />
  </div>

  <template v-else>
    <!--
      The handle, and everything about resizing with it: the floor, the
      ceiling, the keyboard, the width remembered per browser. All of that
      used to be written out here, which is fine for one resizable thing and
      is why the sidebar never became one.
    -->
    <Resizer
      v-model="width"
      :min="MIN"
      :default-size="DEFAULT"
      :max-share="maxShare"
      side="left"
      label="the record"
      remember="onespace.record-pane"
      slot-name="record-resizer"
    />

    <div
      data-slot="record-pane"
      class="flex shrink-0 flex-col overflow-hidden"
      :style="{ width: `${width}px` }"
    >
      <slot name="body" :phone="false" />
    </div>
  </template>
</template>

<script setup>
import { ref } from 'vue'
import Resizer from './Resizer.vue'
import { useIsMobile } from '@/lib/screen'

defineProps({
  /** How wide the pane may get, as a share of the window. */
  maxShare: { type: Number, default: 0.6 },
  /**
   * Whether the record takes the whole content area rather than a column of it.
   *
   * The screen's decision, not this component's: a record that draws itself as
   * a hero and a row of cards is a page, and one that draws itself as a form is
   * something you read beside the list. The host passes what the manifest said.
   */
  page: { type: Boolean, default: false },
})

// Asked here rather than passed in: how a surface renders at a width is the
// surface's own business, and the screen host is not allowed to ask the
// viewport anything — see `test_the_screen_host_shows_the_same_columns_on_every_screen`.
const phone = useIsMobile()

// Narrow enough that a form is still readable, and no narrower: below this the
// labels wrap and the pane is a column of hyphens.
const MIN = 360
const DEFAULT = 480

const width = ref(DEFAULT)
</script>

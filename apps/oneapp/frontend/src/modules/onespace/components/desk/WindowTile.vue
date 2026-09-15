<template>
  <!--
    One open window that no app's tile stands for.

    A picture-in-picture list was the first and a record preview is the reason
    there are now several: five previews are five *records*, and five copies of
    the same document glyph is a row you have to press to read. So a tile shows
    the record's own face where it has one — the same drawing the list cell and
    the breadcrumb use for it — and falls back to the glyph where it does not,
    which is every doctype with no image field.

    **Lit, not filled**, the same as `DockTile` and for the same reason: a line
    under it says which of these is on screen, and a filled chip behind a face
    is a second shape competing with the drawing it is meant to point at.
  -->
  <Button
    variant="ghost"
    :label="name"
    :tooltip="name"
    :data-window-tile="one.id"
    :data-open="lit ? 'yes' : 'no'"
    class="relative !size-9 !p-0"
    @click="press(one.id)"
  >
    <!-- A record's own face: its picture where it has one, its initials where
         it does not — which is what `RecordChip` draws in the list, the trail
         and this window's own title bar. A glyph would be the same drawing for
         every one of them. -->
    <Avatar
      v-if="one.face"
      :image="one.image"
      :label="name"
      shape="square"
      size="lg"
      class="!size-6"
      :class="lit ? '' : 'opacity-50'"
    />
    <Icon
      v-else
      :name="one.icon || 'lucide-app-window'"
      class="size-6"
      :class="lit ? 'text-ink-primary' : 'text-ink-secondary'"
      :aria-hidden="true"
    />

    <!--
      On screen, and under it. Centred out loud: `bottom-0` alone leaves an
      absolute child at the static position it would have had, which beside a
      24px face is a line under the *end* of the tile rather than the middle of
      it — a mark that looks like a mistake rather than a state.
    -->
    <span
      v-if="lit"
      class="pointer-events-none absolute bottom-0 start-1/2 h-0.5 w-3.5 -translate-x-1/2 rounded-full bg-ink-secondary"
    />
  </Button>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar, Button, Icon } from '@/ui'
import { press, visible } from '@/modules/onespace/lib/desk/windows'

const props = defineProps({
  /** One entry from `desk.open` — `{ id, folded, label, icon, image }`. */
  one: { type: Object, required: true },
})

/** Its name, and the id behind it where nobody gave it one. */
const name = computed(() => props.one.label || props.one.id)

/**
 * Whether it is the window on screen — not merely the window not folded away.
 *
 * Previews share a corner, so two of them unfolded is one of them visible and
 * one behind it to the pixel. Lighting both said two windows were open when
 * only one had anything to see. `visible` in `lib/desk/windows.js`.
 */
const lit = computed(() => visible(props.one.id))
</script>

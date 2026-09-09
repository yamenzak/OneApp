<template>
  <!--
    Which silhouette each mode is drawn as.

    A mode is what a network *runs* and a shape is what the map *draws*, and
    they are only the same thing until a customer's Rail turns out to be a light
    rail. The mapping is a document — `Transit Marker Style` — because it is a
    workspace's decision and not a reader's: two screens in one control room
    drawing the same tram differently is a control room having an argument about
    which screen is right.

    Pictures rather than a Select of words, because what is being chosen is a
    picture. Drawn with the same function the map registers its images with, so
    this cannot come to disagree with the thing it sets.
  -->
  <div
    class="flex w-[min(19rem,92vw)] flex-col gap-2 p-3"
    data-slot="marker-picker"
  >
    <p class="text-xs font-medium text-ink-gray-7">{{ __('How each mode is drawn') }}</p>

    <p v-if="!mayWrite" class="text-xs leading-snug text-ink-gray-5">
      {{ __('Somebody who can manage this space can change these.') }}
    </p>

    <div class="flex max-h-[22rem] flex-col gap-0.5 overflow-y-auto">
      <div v-for="one in styles" :key="one.key" class="flex items-center gap-1">
        <span class="w-11 shrink-0 truncate text-xs text-ink-gray-7">{{ one.mode }}</span>
        <!--
          The glyph, which is a different job from the silhouette and sits
          apart from it. The silhouette is what moves on the map; this is what
          this mode is *called* in a list, a chip and a hover card. An emoji
          cannot do the first — fixed colour, and a side elevation turned to a
          bearing is a bus lying down — and is the fastest thing there is at
          the second.
        -->
        <Popover align="end">
          <template #trigger>
            <Button
              variant="ghost"
              :disabled="!mayWrite"
              :tooltip="__('The glyph beside this mode')"
              :aria-label="__('The glyph beside this mode')"
            >
              <span class="text-base leading-none">{{ one.emoji || '·' }}</span>
            </Button>
          </template>
          <template #default>
            <div class="grid w-56 grid-cols-8 gap-0.5 p-2">
              <Button
                v-for="glyph in GLYPHS"
                :key="glyph"
                variant="ghost"
                :aria-label="glyph"
                :class="one.emoji === glyph ? 'bg-surface-gray-3' : ''"
                @click="emit('pick', { mode: one.mode, emoji: glyph })"
              >
                <span class="text-base leading-none">{{ glyph }}</span>
              </Button>
            </div>
          </template>
        </Popover>
        <span class="mx-0.5 h-4 w-px shrink-0 bg-surface-gray-3" />
        <!--
          Thirty-three drawings behind one button rather than thirty-three
          buttons in a row: a row that wraps compares four with three, and the
          point of a picker made of pictures is that they sit side by side.
        -->
        <Popover align="end">
          <template #trigger>
            <Button
              variant="ghost"
              :disabled="!mayWrite"
              :tooltip="__('The silhouette the map draws')"
              :aria-label="__('The silhouette the map draws')"
            >
              <img
                :src="urlFor(one.shape)"
                :alt="nameFor(one.shape)"
                class="size-5 object-contain"
              />
            </Button>
          </template>
          <template #default>
            <div class="grid w-64 grid-cols-6 gap-0.5 p-2">
              <Button
                v-for="shape in shapes"
                :key="shape.key"
                variant="ghost"
                :tooltip="shape.label"
                :aria-label="shape.label"
                :class="one.shape === shape.key ? 'bg-surface-gray-3' : ''"
                @click="emit('pick', { mode: one.mode, shape: shape.key })"
              >
                <img :src="shape.url" :alt="shape.label" class="size-5 object-contain" />
              </Button>
            </div>
          </template>
        </Popover>
        <span class="min-w-0 flex-1 truncate text-2xs text-ink-gray-5">
          {{ nameFor(one.shape) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { artUrl, drawn, FALLBACK, SHAPES } from '@/modules/onemobility/lib/art'
import { SHAPE_NAMES } from '@/modules/onemobility/lib/markers'
import { tokenInk } from '@/modules/onespace/lib/screen/ink'
import { __ } from '@/shared/lib/runtime/translate'
import { Button, Popover } from '@/ui'

defineProps({
  /** `{ mode, key, shape }` per mode, from `markers.marker_styles`. */
  styles: { type: Array, default: () => [] },
  mayWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['pick'])

/**
 * The glyphs on offer. Not "any emoji": a picker of eighteen hundred is a
 * search box, and what somebody is choosing here is one of the forty things
 * that move people. A workspace that wants something else can still type it
 * into the record — this is the shortcut, not the gate.
 */
const GLYPHS = [
  '🚇', '🚊', '🚋', '🚞', '🚝', '🚄', '🚅', '🚆',
  '🚈', '🚉', '🚂', '🚃', '🚌', '🚍', '🚐', '🚎',
  '🚏', '🚑', '🚒', '🚓', '🚕', '🚖', '🚗', '🚙',
  '🚘', '🚚', '🚛', '🚜', '🛺', '🏍️', '🛵', '🚲',
  '🦽', '🦼', '⛴️', '🚢', '🛳️', '🚤', '🛥️', '⛵',
  '🚡', '🚠', '🚦', '🚥', '🚧', '🏎️', '🚀', '🛻',
]

/**
 * Every silhouette, drawn once, in one neutral grey.
 *
 * The same SVGs the map registers rather than a second drawing, so this cannot
 * come to disagree with what it sets. Grey because colour is the *other* axis —
 * on the map the body carries occupancy — and a picker that varied both would
 * be asking two questions in one row.
 */
const INK = '--ink-gray-4'

const shapes = computed(() =>
  SHAPES.map((key) => ({
    key,
    label: SHAPE_NAMES[key] ? SHAPE_NAMES[key]() : key,
    url: artUrl(key, tokenInk(INK, '#a1a1aa')),
  })),
)

function urlFor(shape) {
  // A shape with no drawing behind it would be a broken image; the server's
  // ladder means it should not happen, and this is what happens if it does.
  return artUrl(drawn(shape) ? shape : FALLBACK, tokenInk(INK, '#a1a1aa'))
}
function nameFor(shape) {
  return SHAPE_NAMES[shape] ? SHAPE_NAMES[shape]() : shape
}
</script>

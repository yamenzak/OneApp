<template>
  <!--
    What is on the map, and what it means. Nothing else.

    This card used to carry the controls as well, and it had become a panel with
    a scrollbar in which the actual key — what does orange mean — was below the
    fold. The controls are a rail of icons under the zoom now, and a legend is
    a legend again.

    Read-only is the point, not a limitation: everything here is a *consequence*
    of a choice made elsewhere, and every row is present only while the thing it
    explains is drawn. An empty map with a legend explaining four scales is how
    people learn to stop reading the legend.
  -->
  <div
    class="pointer-events-auto absolute bottom-[11.5rem] start-4 z-10 flex w-52 flex-col gap-2.5
           rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-3 py-2.5 shadow-sm"
    data-slot="network-legend"
  >
    <!-- The overlay's own scale, first and only while one is on. -->
    <div v-if="overlay.kind !== 'none'" class="flex flex-col gap-1">
      <p class="text-xs font-medium text-ink-gray-7">{{ overlay.label() }}</p>
      <div class="flex items-center gap-1.5">
        <span class="shrink-0 text-2xs tabular-nums text-ink-gray-5">{{ low }}</span>
        <span class="flex h-1.5 flex-1 overflow-hidden rounded-full">
          <span
            v-for="(ink, at) in ramp"
            :key="at"
            class="h-full flex-1"
            :style="{ backgroundColor: ink }"
          />
        </span>
        <span class="shrink-0 text-2xs tabular-nums text-ink-gray-5">{{ high }}</span>
      </div>
      <p v-if="overlay.kind === 'surface'" class="text-2xs leading-snug text-ink-gray-5">
        {{ __('Paler where fewer vehicles have been through') }}
      </p>
    </div>

    <!--
      The shapes, before the colours: a marker says two things at once, and a
      key that explains one of them teaches people the other is decoration.

      Only the shapes this network actually draws — a city with buses and
      nothing else should not be told what a ferry looks like.
    -->
    <div v-if="shapes.length && showVehicles" class="flex flex-col gap-1">
      <p class="text-xs font-medium text-ink-gray-7">{{ __('What runs here') }}</p>
      <div v-for="one in shapes" :key="one.key" class="flex items-center gap-2">
        <!-- Larger than the map draws them: a key is read at a glance, and the
             marker's own size is a compromise with how many of them share the
             screen, which a legend row is not. -->
        <img :src="one.url" :alt="one.label" class="size-6 shrink-0 object-contain" />
        <span class="truncate text-2xs text-ink-gray-6">{{ one.label }}</span>
      </div>
    </div>

    <div v-if="showVehicles" class="flex flex-col gap-1">
      <p class="text-xs font-medium text-ink-gray-7">{{ __('How full it is') }}</p>
      <div v-for="band in bands" :key="band.key" class="flex items-center gap-2">
        <span class="size-2 shrink-0 rounded-full" :style="{ backgroundColor: band.ink }" />
        <span class="flex-1 truncate text-2xs text-ink-gray-6">{{ band.label }}</span>
        <span v-if="band.floor > 0" class="text-2xs tabular-nums text-ink-gray-5">
          {{ band.floor }}%+
        </span>
      </div>
    </div>

    <!-- The two things a stop's drawing says that nothing else does. -->
    <div v-if="showStops" class="flex flex-col gap-1">
      <div class="flex items-center gap-2">
        <span class="size-2.5 shrink-0 rounded-full border-2 border-outline-amber-3
                     bg-surface-elevation-2" />
        <span class="truncate text-2xs text-ink-gray-6">{{ __('Stop nobody declared') }}</span>
      </div>
      <div class="flex items-center gap-2">
        <span class="flex size-2.5 shrink-0 items-center justify-center rounded-full border-2
                     border-outline-gray-3 bg-surface-elevation-2">
          <span class="size-1 rounded-full bg-surface-gray-7" />
        </span>
        <span class="truncate text-2xs text-ink-gray-6">
          {{ __('More than one line stops here') }}
        </span>
      </div>
    </div>

    <!-- What has been faded away, said in words. -->
    <p v-if="isolated" class="border-t border-outline-gray-1 pt-2 text-2xs leading-snug
                              text-ink-gray-5">
      {{ __('Everything but {0} is dimmed.', [isolated.label]) }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { SHAPE_NAMES, swatchUrl } from '@/modules/onemobility/lib/markers'
import { bandInk, casingInk, OCCUPANCY } from '@/modules/onemobility/lib/palette'
import { tokenInk } from '@/modules/onespace/lib/screen/ink'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The resolved overlay from `lib/layers`, `kind: 'none'` when there is none. */
  overlay: { type: Object, required: true },
  ramp: { type: Array, default: () => [] },
  low: { type: String, default: '' },
  high: { type: String, default: '' },
  /** The silhouettes actually on the map, as shape keys. */
  drawn: { type: Array, default: () => [] },
  showStops: { type: Boolean, default: true },
  showVehicles: { type: Boolean, default: true },
  isolated: { type: Object, default: null },
})

/**
 * Painted with the same `vehicleMarker` the map registers, so the key cannot
 * come to disagree with the thing it explains. One neutral grey, because
 * colour is the *other* axis and varying both here teaches neither.
 */
const shapes = computed(() => {
  const ring = casingInk()
  const neutral = tokenInk('--ink-gray-4', '#999999')
  return props.drawn.map((key) => ({
    key,
    label: SHAPE_NAMES[key] ? SHAPE_NAMES[key]() : key,
    url: swatchUrl(key, neutral, ring, 2),
  }))
})

const bands = computed(() =>
  OCCUPANCY.map((band) => ({
    key: band.key,
    floor: band.floor,
    label: band.label(),
    ink: bandInk(band),
  })),
)
</script>

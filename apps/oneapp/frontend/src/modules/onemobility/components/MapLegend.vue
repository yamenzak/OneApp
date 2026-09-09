<template>
  <!--
    What is on the map, and what it means. Nothing else.

    This card used to carry the controls as well, and it had become a panel with
    a scrollbar in which the actual key — what does orange mean — was below the
    fold. The controls are a rail of icons under the zoom now, and a legend is
    a legend again.

    **Small by default, complete on demand.** The full key ran to three headed
    lists and took two thirds of the height of the map, which is a lot of screen
    for something a reader learns once and then remembers. So the shapes are a
    row of swatches and the load is one bar, and the names behind them are a
    click away. The overlay's own scale stays open at all times, because it is
    the one thing here that *changes*.

    Read-only either way, and that is the point rather than a limitation:
    everything here is a consequence of a choice made elsewhere, and every row
    is present only while the thing it explains is drawn. An empty map with a
    legend explaining four scales is how people learn to stop reading legends.
  -->
  <div
    class="pointer-events-auto absolute bottom-[11.5rem] start-4 z-10 flex w-48 flex-col gap-2
           rounded-6 border border-outline-gray-2 bg-surface-elevation-2 px-2.5 py-2 shadow-sm"
    data-slot="network-legend"
  >
    <!-- The overlay's own scale, first and only while one is on. -->
    <div v-if="overlay.kind !== 'none'" class="flex flex-col gap-1">
      <p class="text-2xs font-medium text-ink-gray-7">{{ overlay.label() }}</p>
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
      The shapes, as a row rather than a list. Only the ones this network
      actually draws — a city with buses and nothing else should not be told
      what a ferry looks like — and at twenty-eight pixels, which is about where
      these drawings stop being a tick and start being a vehicle.
    -->
    <div v-if="shapes.length && showVehicles" class="flex flex-wrap items-center gap-1">
      <Tooltip v-for="one in shapes" :key="one.key" :text="one.label">
        <img :src="one.url" :alt="one.label" class="size-7 shrink-0 object-contain" />
      </Tooltip>
    </div>

    <!--
      And the load as one bar rather than five named rows. The ordinal scale is
      what a reader needs at a glance; which step is called "standing" is what
      they need once, and it is under the toggle.
    -->
    <div v-if="showVehicles" class="flex flex-col gap-1">
      <span class="flex h-1.5 w-full overflow-hidden rounded-full">
        <span
          v-for="band in scale"
          :key="band.key"
          class="h-full flex-1"
          :style="{ backgroundColor: band.ink }"
        />
      </span>
      <div class="flex items-baseline justify-between text-2xs text-ink-gray-5">
        <span>{{ scale[0].label }}</span>
        <span>{{ scale[scale.length - 1].label }}</span>
      </div>
    </div>

    <Button
      class="-mx-1 justify-start"
      variant="ghost"
      size="sm"
      :label="open ? __('Less') : __('What this means')"
      :icon-left="open ? 'lucide-chevron-down' : 'lucide-chevron-right'"
      @click="open = !open"
    />

    <div v-if="open" class="flex flex-col gap-2 border-t border-outline-gray-1 pt-2">
      <div v-if="shapes.length && showVehicles" class="flex flex-col gap-0.5">
        <p class="text-2xs font-medium text-ink-gray-7">{{ __('What runs here') }}</p>
        <div v-for="one in shapes" :key="one.key" class="flex items-center gap-1.5">
          <img :src="one.url" :alt="one.label" class="size-5 shrink-0 object-contain" />
          <span class="truncate text-2xs text-ink-gray-6">{{ one.label }}</span>
        </div>
      </div>

      <div v-if="showVehicles" class="flex flex-col gap-0.5">
        <p class="text-2xs font-medium text-ink-gray-7">{{ __('How full it is') }}</p>
        <div v-for="band in bands" :key="band.key" class="flex items-center gap-1.5">
          <span class="size-2 shrink-0 rounded-full" :style="{ backgroundColor: band.ink }" />
          <span class="flex-1 truncate text-2xs text-ink-gray-6">{{ band.label }}</span>
          <span v-if="band.floor > 0" class="text-2xs tabular-nums text-ink-gray-5">
            {{ band.floor }}%+
          </span>
        </div>
      </div>

      <!-- The two things a stop's drawing says that nothing else does. -->
      <div v-if="showStops" class="flex flex-col gap-1">
        <div class="flex items-center gap-1.5">
          <span class="size-2.5 shrink-0 rounded-full border-2 border-outline-amber-3
                       bg-surface-elevation-2" />
          <span class="truncate text-2xs text-ink-gray-6">{{ __('Stop nobody declared') }}</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="flex size-2.5 shrink-0 items-center justify-center rounded-full border-2
                       border-outline-gray-3 bg-surface-elevation-2">
            <span class="size-1 rounded-full bg-surface-gray-7" />
          </span>
          <span class="truncate text-2xs text-ink-gray-6">
            {{ __('More than one line stops here') }}
          </span>
        </div>
      </div>
    </div>

    <!--
      That these are claims rather than readings, and what they rest on.
      First, above everything, because it changes how every other row on the
      card should be read — a spread quietly redefined as a forecast is the
      kind of thing a reader finds out afterwards.
    -->
    <div v-if="expected" class="flex flex-col gap-0.5 border-b border-outline-gray-1 pb-2">
      <div class="flex items-center gap-1.5">
        <span class="size-2 shrink-0 rounded-full bg-surface-amber-3" />
        <p class="text-2xs font-medium text-ink-gray-7">{{ __('What is expected') }}</p>
      </div>
      <p class="text-2xs leading-snug text-ink-gray-5">{{ expected }}</p>
    </div>

    <!-- What has been faded away, said in words. -->
    <p v-if="isolated" class="border-t border-outline-gray-1 pt-2 text-2xs leading-snug
                              text-ink-gray-5">
      {{ __('Everything but {0} is dimmed.', [isolated.label]) }}
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import { artUrl } from '@/modules/onemobility/lib/art'
import { SHAPE_NAMES } from '@/modules/onemobility/lib/markers'
import { bandInk, OCCUPANCY } from '@/modules/onemobility/lib/palette'
import { tokenInk } from '@/modules/onespace/lib/screen/ink'
import { __ } from '@/shared/lib/runtime/translate'
import { Button, Tooltip } from '@/ui'

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
  /** One sentence when the clock is past now, empty otherwise. */
  expected: { type: String, default: '' },
})

const open = ref(false)

/**
 * The same drawings the map registers, so the key cannot come to disagree with
 * the thing it explains.
 *
 * `gray-4`, chosen by rendering every grey against every size: paler and the
 * drawings' own light detail disappears into the body, darker and their dark
 * detail does. On the map the body is an occupancy colour and the question does
 * not arise.
 */
const shapes = computed(() => {
  const neutral = tokenInk('--ink-gray-4', '#a1a1aa')
  return props.drawn.map((key) => ({
    key,
    label: SHAPE_NAMES[key] ? SHAPE_NAMES[key]() : key,
    url: artUrl(key, neutral),
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

/**
 * The bar leaves out "not counted".
 *
 * That band is a real state and belongs in the named list, but it is not a step
 * on the scale: a neutral grey at one end of a green-to-red ramp says the two
 * are the same kind of thing, and a reader who believes that reads an unknown
 * as an empty vehicle.
 */
const scale = computed(() => bands.value.filter((band) => band.floor >= 0))
</script>
